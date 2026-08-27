/** WYSIWYG field for question/message text the bot sends to candidates, built on
 *  `@mdxeditor/editor`.
 *
 *  The toolbar is deliberately restricted to the formatting `app/bot/markup.py` can actually
 *  render in Telegram — bold, italic, underline, strikethrough, inline code, link, emoji —
 *  even though mdxeditor itself supports far more (headings, lists, tables, images). Anything
 *  beyond that set would let an HR author something the editor renders nicely but Telegram
 *  shows as literal `#`/`-` characters, breaking the one guarantee this field exists for: what
 *  the author sees here is what the candidate sees there. Headings/lists/quotes/thematic-break
 *  plugins are still registered, silently, with no toolbar button — not to offer the feature,
 *  but so that legacy content (or an HR who happens to type a line starting with `#` or `-`)
 *  imports without throwing instead of erroring out the whole field.
 *
 *  What actually reaches `onChange` — and gets saved to the database — is still this app's
 *  own narrow Markdown grammar, not raw CommonMark: `toEditorMarkdown`/`fromEditorMarkdown`
 *  (src/lib/markdown.ts) adapt at the boundary, mainly to keep `__underline__` intact (see
 *  that file for why CommonMark can't represent it directly).
 */
import "@mdxeditor/editor/style.css";

import {
  BoldItalicUnderlineToggles,
  type CodeBlockEditorDescriptor,
  type CodeBlockEditorProps,
  codeBlockPlugin,
  CodeToggle,
  CreateLink,
  defaultSvgIcons,
  headingsPlugin,
  type IconKey,
  linkDialogPlugin,
  linkPlugin,
  listsPlugin,
  MDXEditor,
  type MDXEditorMethods,
  quotePlugin,
  StrikeThroughSupSubToggles,
  thematicBreakPlugin,
  toolbarPlugin,
} from "@mdxeditor/editor";
import {
  Bold,
  Check,
  Code,
  Copy,
  ExternalLink,
  Italic,
  Link as LinkIcon,
  Pencil,
  Smile,
  Strikethrough,
  Underline,
  Unlink,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { EMOJI_CATEGORIES } from "@/lib/emoji";
import { fromEditorMarkdown, markdownToPreviewHtml, toEditorMarkdown } from "@/lib/markdown";
import { cn } from "@/lib/utils";

const CUSTOM_ICONS: Partial<Record<IconKey, React.ReactElement>> = {
  format_bold: <Bold className="h-3.5 w-3.5" />,
  format_italic: <Italic className="h-3.5 w-3.5" />,
  format_underlined: <Underline className="h-3.5 w-3.5" />,
  strikeThrough: <Strikethrough className="h-3.5 w-3.5" />,
  code: <Code className="h-3.5 w-3.5" />,
  link: <LinkIcon className="h-3.5 w-3.5" />,
  edit: <Pencil className="h-3.5 w-3.5" />,
  link_off: <Unlink className="h-3.5 w-3.5" />,
  content_copy: <Copy className="h-3.5 w-3.5" />,
  check: <Check className="h-3.5 w-3.5" />,
  open_in_new: <ExternalLink className="h-3.5 w-3.5" />,
};

function iconComponentFor(name: IconKey) {
  return CUSTOM_ICONS[name] ?? defaultSvgIcons[name];
}

/** No toolbar button ever creates a fenced code block, but a question saved before this
 *  editor existed could contain one — mdxeditor throws on import if a code block has no
 *  matching descriptor at all, so this plain, read-only fallback exists purely so that
 *  content still loads instead of erroring out the whole field. */
function LegacyCodeBlockEditor({ code }: CodeBlockEditorProps) {
  return (
    <textarea
      className="w-full resize-none rounded bg-muted p-2 font-mono text-sm"
      defaultValue={code}
      readOnly
      rows={Math.max(1, code.split("\n").length)}
    />
  );
}

const CODE_BLOCK_DESCRIPTORS: CodeBlockEditorDescriptor[] = [
  { priority: -1, match: () => true, Editor: LegacyCodeBlockEditor },
];

function useDarkMode(): boolean {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains("dark")),
    );
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return dark;
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
  const dark = useDarkMode();
  const editorRef = useRef<MDXEditorMethods>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const lastEmitted = useRef(value);

  // mdxeditor has no prop for the contentEditable element's `id` — set it directly on the
  // real DOM node so `<Label htmlFor={id}>` on the call sites still focuses the field, same
  // as it did when this component rendered the contentEditable div itself.
  useEffect(() => {
    if (!id) return;
    const editable = wrapperRef.current?.querySelector<HTMLElement>('[contenteditable="true"]');
    if (editable) editable.id = id;
  }, [id]);

  const [emojiOpen, setEmojiOpen] = useState(false);
  const [emojiCategory, setEmojiCategory] = useState(EMOJI_CATEGORIES[0].key);

  // Controlled-value sync: the `markdown` prop is only read once, at mount (mdxeditor's own
  // docs call this out), so switching language tabs or loading a different question has to
  // push the new value in imperatively via `setMarkdown` — but only when it changed from
  // *outside* the editor, or every keystroke's own onChange echo would fight the caret.
  useEffect(() => {
    if (value === lastEmitted.current) return;
    lastEmitted.current = value;
    editorRef.current?.setMarkdown(toEditorMarkdown(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  function emitChange(markdown: string, initialMarkdownNormalize: boolean) {
    // mdxeditor fires onChange once right after mount with the *re-serialized* initial value —
    // not a real edit. Propagating that would silently rewrite the stored text (through the
    // full CommonMark exporter, not this app's narrow parser) the moment a form is merely
    // opened, before the author has touched anything.
    if (initialMarkdownNormalize) return;
    const next = fromEditorMarkdown(markdown);
    lastEmitted.current = next;
    onChange(next);
  }

  function insertEmoji(emoji: string) {
    editorRef.current?.insertMarkdown(emoji);
  }

  function mdxTranslation(key: string, fallback: string): string {
    const map: Record<string, string> = {
      "toolbar.bold": t("markdown.bold"),
      "toolbar.removeBold": t("markdown.removeBold"),
      "toolbar.italic": t("markdown.italic"),
      "toolbar.removeItalic": t("markdown.removeItalic"),
      "toolbar.underline": t("markdown.underline"),
      "toolbar.removeUnderline": t("markdown.removeUnderline"),
      "toolbar.strikethrough": t("markdown.strike"),
      "toolbar.removeStrikethrough": t("markdown.removeStrike"),
      "toolbar.inlineCode": t("markdown.code"),
      "toolbar.removeInlineCode": t("markdown.removeCode"),
      "createLink.url": t("markdown.linkUrlLabel"),
      "createLink.saveTooltip": t("markdown.linkApply"),
      "createLink.cancelTooltip": t("markdown.cancel"),
      "dialogControls.save": t("markdown.linkApply"),
      "dialogControls.cancel": t("markdown.cancel"),
      "linkPreview.edit": t("markdown.link"),
      "linkPreview.remove": t("markdown.linkRemove"),
    };
    return map[key] ?? fallback;
  }

  return (
    <div
      ref={wrapperRef}
      className={cn("space-y-1.5", className)}
      style={{ ["--mf-min-h" as string]: `${rows * 1.5 + 1}rem` }}
    >
      <MDXEditor
        ref={editorRef}
        markdown={toEditorMarkdown(value)}
        onChange={emitChange}
        placeholder={
          placeholder ? (
            // The placeholder in a translation tab is the base language's own saved text,
            // rendered through the same converter used for the base grammar's live preview —
            // so it previews as bold/linked/etc. too, not as raw `**markdown**` syntax.
            <span dangerouslySetInnerHTML={{ __html: markdownToPreviewHtml(placeholder) }} />
          ) : undefined
        }
        contentEditableClassName="mf-editable"
        className={cn("mf-root", dark && "dark-theme dark-editor")}
        toMarkdownOptions={{ emphasis: "_" }}
        iconComponentFor={iconComponentFor}
        translation={mdxTranslation}
        plugins={[
          headingsPlugin(),
          listsPlugin(),
          quotePlugin(),
          thematicBreakPlugin(),
          linkPlugin({ disableAutoLink: true }),
          linkDialogPlugin(),
          codeBlockPlugin({ codeBlockEditorDescriptors: CODE_BLOCK_DESCRIPTORS }),
          toolbarPlugin({
            toolbarContents: () => (
              <>
                <BoldItalicUnderlineToggles />
                <StrikeThroughSupSubToggles options={["Strikethrough"]} />
                <CodeToggle />
                <CreateLink />

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
                  <PopoverContent className="w-72 p-2" onOpenAutoFocus={(e) => e.preventDefault()}>
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
              </>
            ),
          }),
        ]}
      />
    </div>
  );
}
