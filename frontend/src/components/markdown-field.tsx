/** WYSIWYG-ish field for question text the bot sends to candidates.
 *
 *  The author never sees Markdown syntax and never has to switch to a separate preview to
 *  find out whether their `**` landed in the right place — the editing surface itself
 *  always shows bold as bold, a link as a link, etc. Selecting text and clicking "Bold"
 *  behaves like a word processor's bold button, operating on the DOM directly (wrap/unwrap
 *  via the Selection/Range API — deliberately not `execCommand`, which produces
 *  browser-inconsistent markup we would then have to normalise anyway).
 *
 *  What actually gets sent to `onChange` — and saved to the database — is still plain
 *  Markdown: every edit is serialized back through `htmlToMarkdown` (src/lib/markdown.ts),
 *  the same grammar `app/bot/markup.py` parses on the backend. The DOM is purely a
 *  rendering of that Markdown; it never becomes the source of truth.
 */

import {
  Bold,
  Code,
  Italic,
  Link as LinkIcon,
  Smile,
  Strikethrough,
  Underline,
  Unlink,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/misc";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { EMOJI_CATEGORIES } from "@/lib/emoji";
import { htmlToMarkdown, markdownToPreviewHtml } from "@/lib/markdown";
import { cn } from "@/lib/utils";

// Tag name -> the toolbar entry that toggles it. Order here is the toolbar's left-to-right
// order.
const INLINE_ACTIONS = [
  { tag: "B", icon: Bold, labelKey: "bold", placeholderKey: "boldText" },
  { tag: "I", icon: Italic, labelKey: "italic", placeholderKey: "italicText" },
  { tag: "U", icon: Underline, labelKey: "underline", placeholderKey: "underlineText" },
  { tag: "S", icon: Strikethrough, labelKey: "strike", placeholderKey: "strikeText" },
  { tag: "CODE", icon: Code, labelKey: "code", placeholderKey: "codeText" },
] as const;

/** Walk up from `node` to the nearest ancestor with this tag name, stopping at (and not
 *  going past) `root`. */
function closestWithin(node: Node, tagName: string, root: HTMLElement): HTMLElement | null {
  let el: Node | null = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  while (el && el !== root) {
    if ((el as HTMLElement).tagName === tagName) return el as HTMLElement;
    el = el.parentElement;
  }
  return null;
}

/** If the whole selection is exactly one element's text content, that is the element to
 *  toggle off. Handles both a single-text-node run and a formatted range that itself
 *  contains nested formatting (`<b>plain <i>and italic</i></b>`, selected end to end). */
function findExactWrap(range: Range, tagName: string, root: HTMLElement): HTMLElement | null {
  const el = closestWithin(range.commonAncestorContainer, tagName, root);
  return el && el.textContent === range.toString() ? el : null;
}

function findEnclosingAnchor(range: Range, root: HTMLElement): HTMLAnchorElement | null {
  return closestWithin(range.commonAncestorContainer, "A", root) as HTMLAnchorElement | null;
}

/** Remove every descendant with this tag, keeping its children in place — used before
 *  wrapping a fresh selection so the same mark can never end up nested inside itself
 *  (which would serialize to unbalanced markers like `**a **b** c**`). */
function stripNestedTag(root: DocumentFragment | HTMLElement, tagName: string): void {
  root.querySelectorAll(tagName).forEach((el) => {
    const parent = el.parentNode;
    if (!parent) return;
    while (el.firstChild) parent.insertBefore(el.firstChild, el);
    parent.removeChild(el);
  });
}

function selectContents(node: Node): void {
  const selection = window.getSelection();
  if (!selection) return;
  const range = document.createRange();
  range.selectNodeContents(node);
  selection.removeAllRanges();
  selection.addRange(range);
}

function selectAcross(nodes: Node[]): void {
  if (!nodes.length) return;
  const selection = window.getSelection();
  if (!selection) return;
  const range = document.createRange();
  range.setStartBefore(nodes[0]);
  range.setEndAfter(nodes[nodes.length - 1]);
  selection.removeAllRanges();
  selection.addRange(range);
}

/** The one function every toolbar button (other than Link) calls. Three cases:
 *  nothing selected -> insert a wrapped placeholder and select it, ready to type over;
 *  selection exactly matches one existing tag of this type -> unwrap (toggle off);
 *  otherwise -> wrap the selection fresh, after stripping any same-tag nesting inside it.
 */
function toggleInline(root: HTMLElement, tagName: string, placeholder: string): void {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return;
  const range = selection.getRangeAt(0);
  if (!root.contains(range.commonAncestorContainer)) return;

  if (range.collapsed) {
    const wrapper = document.createElement(tagName);
    wrapper.textContent = placeholder;
    range.insertNode(wrapper);
    selectContents(wrapper);
    return;
  }

  const exact = findExactWrap(range, tagName, root);
  if (exact) {
    const inner = document.createRange();
    inner.selectNodeContents(exact);
    const frag = inner.extractContents();
    const nodes = Array.from(frag.childNodes);
    exact.replaceWith(frag);
    selectAcross(nodes);
    return;
  }

  const frag = range.extractContents();
  stripNestedTag(frag, tagName);
  const wrapper = document.createElement(tagName);
  wrapper.appendChild(frag);
  range.insertNode(wrapper);
  selectContents(wrapper);
}

export function MarkdownField({
  id,
  value,
  onChange,
  placeholder,
  rows = 4,
  className,
}: {
  id?: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
}) {
  const { t } = useTranslation();
  const rootRef = useRef<HTMLDivElement>(null);
  const lastEmitted = useRef<string | null>(null);
  const [empty, setEmpty] = useState(!value);

  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const savedRangeRef = useRef<Range | null>(null);
  const editingAnchorRef = useRef<HTMLAnchorElement | null>(null);
  const linkUrlInputRef = useRef<HTMLInputElement>(null);

  const [emojiOpen, setEmojiOpen] = useState(false);
  const [emojiCategory, setEmojiCategory] = useState(EMOJI_CATEGORIES[0].key);

  const emit = () => {
    const el = rootRef.current;
    if (!el) return;
    const markdown = htmlToMarkdown(el);
    lastEmitted.current = markdown;
    setEmpty(!el.textContent?.length);
    onChange(markdown);
  };

  // Controlled-value sync: only re-render the DOM from `value` when it changed from
  // *outside* this component (switching language tabs, loading a different question).
  // Re-rendering on every keystroke — which is what a naive `el.innerHTML = ...` on every
  // prop change would do, since our own `onChange` echoes straight back into `value` —
  // would reset the caret to the start of the field on every character typed.
  useEffect(() => {
    const el = rootRef.current;
    if (!el || value === lastEmitted.current) return;
    el.innerHTML = markdownToPreviewHtml(value);
    lastEmitted.current = value;
    setEmpty(!value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  function runToggle(tag: string, placeholderText: string) {
    const el = rootRef.current;
    if (!el) return;
    el.focus();
    toggleInline(el, tag, placeholderText);
    emit();
  }

  /** Inserts at the live caret, same as a keystroke would — the popover never takes focus
   *  (every button in it, like every other toolbar button, swallows its own mousedown), so
   *  the selection captured here is still the one the author left in the text. Left open
   *  after inserting so several emoji can be picked in a row, the way Telegram's own picker
   *  behaves. */
  function insertEmoji(emoji: string) {
    const el = rootRef.current;
    if (!el) return;
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (!el.contains(range.commonAncestorContainer)) return;

    range.deleteContents();
    const node = document.createTextNode(emoji);
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    emit();
  }

  function openLinkPopover() {
    const el = rootRef.current;
    const selection = window.getSelection();
    if (!el || !selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (!el.contains(range.commonAncestorContainer)) return;

    const anchor = findEnclosingAnchor(range, el);
    if (anchor) {
      const full = document.createRange();
      full.selectNodeContents(anchor);
      savedRangeRef.current = full;
      editingAnchorRef.current = anchor;
      setLinkUrl(anchor.getAttribute("href") ?? "");
    } else {
      savedRangeRef.current = range.cloneRange();
      editingAnchorRef.current = null;
      setLinkUrl("https://");
    }
    setLinkOpen(true);
  }

  function applyLink() {
    const el = rootRef.current;
    const range = savedRangeRef.current;
    if (!el || !range) return;
    const url = linkUrl.trim();
    if (!url) return;

    const label = range.toString() || t("markdown.linkText");
    const anchor = document.createElement("a");
    anchor.setAttribute("href", url);
    anchor.textContent = label;

    range.deleteContents();
    range.insertNode(anchor);

    setLinkOpen(false);
    savedRangeRef.current = null;
    editingAnchorRef.current = null;
    el.focus();
    selectContents(anchor);
    emit();
  }

  function removeLink() {
    const anchor = editingAnchorRef.current;
    if (!anchor) {
      setLinkOpen(false);
      return;
    }
    const text = document.createTextNode(anchor.textContent ?? "");
    anchor.replaceWith(text);
    setLinkOpen(false);
    savedRangeRef.current = null;
    editingAnchorRef.current = null;
    rootRef.current?.focus();
    emit();
  }

  /** Enter must insert a single `<br>`, never a new block element — a `<div>`-per-line
   *  structure (what browsers do by default) would still round-trip through the
   *  serializer's DIV fallback, but a plain `<br>` matches `markdownToPreviewHtml`'s own
   *  output exactly, so what the author sees never shifts on the next load. */
  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    // `keyCode` is a fallback for input sources (some IMEs, remote-desktop/accessibility
    // input, embedded webviews) that leave `.key` unpopulated — a real keyboard always
    // reports "Enter" correctly, but nothing is lost by also accepting the numeric code.
    if (e.key !== "Enter" && e.keyCode !== 13) return;
    e.preventDefault();
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const br = document.createElement("br");
    range.insertNode(br);
    // An empty text node right after the <br> gives the caret an unambiguous anchor.
    // Positioning it directly "after the <br>" as a parent/offset pair (setStartAfter) is
    // exactly the state Chrome resolves inconsistently when the <br> is the last node in
    // the block: it snaps the caret back onto the preceding line, so the next character
    // typed lands *before* the <br> instead of after it. An empty text node is a genuine
    // position inside the new line, and contributes nothing to the serialized Markdown
    // either way (an empty string concatenates to nothing).
    const anchor = document.createTextNode("");
    br.after(anchor);
    range.setStart(anchor, 0);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    emit();
  }

  /** Paste is always plain text. Accepting the source's HTML would mean sanitising and
   *  reconciling arbitrary third-party markup against our own tag set — plain text sidesteps
   *  that entirely, and a pasted `**bold**`-looking string just becomes literal characters
   *  (identical to what pasting into the old raw-textarea field did). */
  function handlePaste(e: React.ClipboardEvent<HTMLDivElement>) {
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();

    // Built off-DOM and inserted in one call so the lines land in the right order — a loop
    // of repeated `range.insertNode()` calls on the same collapsed range would each insert
    // at the same boundary and come out reversed.
    const fragment = document.createDocumentFragment();
    text.split("\n").forEach((line, i) => {
      if (i > 0) fragment.appendChild(document.createElement("br"));
      if (line) fragment.appendChild(document.createTextNode(line));
    });
    const lastNode = fragment.lastChild;
    range.insertNode(fragment);

    if (lastNode) {
      range.setStartAfter(lastNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }
    emit();
  }

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex flex-wrap items-center gap-1 rounded-t-md border border-b-0 bg-muted/40 p-1">
        {INLINE_ACTIONS.map(({ tag, icon: Icon, labelKey, placeholderKey }) => (
          <Button
            key={tag}
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            title={t(`markdown.${labelKey}`)}
            aria-label={t(`markdown.${labelKey}`)}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => runToggle(tag, t(`markdown.${placeholderKey}`))}
          >
            <Icon className="h-3.5 w-3.5" />
          </Button>
        ))}

        <Popover
          open={linkOpen}
          onOpenChange={(open) => {
            if (!open) {
              setLinkOpen(false);
              savedRangeRef.current = null;
              editingAnchorRef.current = null;
            }
          }}
        >
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title={t("markdown.link")}
              aria-label={t("markdown.link")}
              onMouseDown={(e) => e.preventDefault()}
              onClick={openLinkPopover}
            >
              <LinkIcon className="h-3.5 w-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            onOpenAutoFocus={(e) => {
              e.preventDefault();
              linkUrlInputRef.current?.focus();
              linkUrlInputRef.current?.select();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="markdown-link-url" className="text-xs">
                {t("markdown.linkUrlLabel")}
              </Label>
              <Input
                id="markdown-link-url"
                ref={linkUrlInputRef}
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    applyLink();
                  }
                }}
                className="h-8 text-sm"
              />
              <div className="flex items-center justify-between pt-1">
                {editingAnchorRef.current ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs text-destructive hover:text-destructive"
                    onClick={removeLink}
                  >
                    <Unlink className="h-3.5 w-3.5" />
                    {t("markdown.linkRemove")}
                  </Button>
                ) : (
                  <span />
                )}
                <Button
                  type="button"
                  size="sm"
                  className="h-7 px-3 text-xs"
                  disabled={!linkUrl.trim()}
                  onClick={applyLink}
                >
                  {t("markdown.linkApply")}
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>

        <Popover open={emojiOpen} onOpenChange={setEmojiOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              title={t("markdown.emoji")}
              aria-label={t("markdown.emoji")}
              onMouseDown={(e) => e.preventDefault()}
            >
              <Smile className="h-3.5 w-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="w-72 p-2"
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <div className="flex flex-wrap gap-0.5 border-b pb-2">
              {EMOJI_CATEGORIES.map((category) => (
                <Button
                  key={category.key}
                  type="button"
                  variant="ghost"
                  size="icon"
                  className={cn(
                    "h-7 w-7 text-base",
                    emojiCategory === category.key && "bg-muted",
                  )}
                  title={t(`markdown.emojiCategories.${category.key}`)}
                  aria-label={t(`markdown.emojiCategories.${category.key}`)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setEmojiCategory(category.key)}
                >
                  {category.icon}
                </Button>
              ))}
            </div>
            <div className="grid max-h-48 grid-cols-8 gap-0.5 overflow-y-auto pt-2">
              {EMOJI_CATEGORIES.find((c) => c.key === emojiCategory)?.emojis.map(
                (emoji, i) => (
                  <button
                    key={i}
                    type="button"
                    className="rounded text-lg leading-none hover:bg-muted"
                    style={{ aspectRatio: "1", padding: "0.35rem" }}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => insertEmoji(emoji)}
                  >
                    {emoji}
                  </button>
                ),
              )}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      <div className="relative">
        <div
          id={id}
          ref={rootRef}
          contentEditable
          suppressContentEditableWarning
          onInput={emit}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          style={{ minHeight: `${rows * 1.5 + 1}rem` }}
          className={cn(
            "w-full resize-y overflow-y-auto rounded-b-md border px-3 py-2 text-sm shadow-sm",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            "[&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.85em] [&_pre]:rounded [&_pre]:bg-muted [&_pre]:p-2 [&_pre]:font-mono [&_pre]:text-[0.85em]",
          )}
        />
        {empty && placeholder && (
          // A native `placeholder` attribute doesn't exist for contentEditable, and relying
          // on CSS `:empty` is unreliable — Chrome leaves a stray `<br>` behind after the
          // last character is deleted, so `:empty` stops matching right when the placeholder
          // should reappear. Tracking emptiness in React state sidesteps that.
          <div
            className="pointer-events-none absolute inset-0 overflow-hidden px-3 py-2 text-sm text-muted-foreground"
            // The placeholder in a translation tab is the base language's own saved text,
            // rendered through the same converter as the live editor — so it previews as
            // bold/linked/etc. too, not as raw `**markdown**` syntax.
            dangerouslySetInnerHTML={{ __html: markdownToPreviewHtml(placeholder) }}
          />
        )}
      </div>
    </div>
  );
}
