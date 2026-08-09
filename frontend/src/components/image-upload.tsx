/** Image picker: click or drop a file, see a preview, clear it.
 *
 *  Uploads immediately and hands the caller back a URL, so the surrounding form still only
 *  ever deals with a `photo_url` string — the same shape the API stores. That keeps the
 *  upload out of the form's save path: a slow upload never blocks typing, and a failed one
 *  never loses the rest of the draft.
 */

import { ImageIcon, Loader2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/misc";
import { uploadImage } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCEPT = "image/jpeg,image/png,image/webp,image/gif";

export function ImageUpload({
  label,
  value,
  onChange,
  className,
}: {
  label: string;
  value: string | null | undefined;
  onChange: (url: string | null) => void;
  className?: string;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [broken, setBroken] = useState(false);

  async function send(file: File) {
    setBusy(true);
    try {
      const { url } = await uploadImage(file);
      setBroken(false);
      onChange(url);
      toast.success(t("upload.done"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("common.error"));
    } finally {
      setBusy(false);
      // Reset so picking the same file twice still fires a change event.
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className={cn("space-y-2", className)}>
      <Label>{label}</Label>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void send(file);
        }}
      />

      {value && !broken ? (
        <div className="relative w-fit">
          <img
            src={value}
            alt=""
            className="h-28 w-28 rounded-lg border object-cover"
            onError={() => setBroken(true)}
          />
          <Button
            type="button"
            variant="destructive"
            size="icon"
            className="absolute -right-2 -top-2 h-6 w-6 rounded-full"
            aria-label={t("upload.remove")}
            onClick={() => {
              setBroken(false);
              onChange(null);
            }}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files?.[0];
            if (file) void send(file);
          }}
          className={cn(
            "flex h-28 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm transition-colors",
            dragging
              ? "border-primary bg-primary/5 text-primary"
              : "text-muted-foreground hover:border-primary/50 hover:text-foreground",
            busy && "pointer-events-none opacity-60",
          )}
        >
          {busy ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              {t("upload.uploading")}
            </>
          ) : (
            <>
              <Upload className="h-5 w-5" />
              {t("upload.prompt")}
              <span className="text-xs">{t("upload.hint")}</span>
            </>
          )}
        </button>
      )}

      {/* A URL that 404s would otherwise render as a broken-image glyph with no explanation. */}
      {value && broken && (
        <p className="flex items-center gap-1.5 text-xs text-destructive">
          <ImageIcon className="h-3 w-3" />
          {t("upload.broken")}
          <button
            type="button"
            className="underline"
            onClick={() => {
              setBroken(false);
              onChange(null);
            }}
          >
            {t("upload.remove")}
          </button>
        </p>
      )}
    </div>
  );
}
