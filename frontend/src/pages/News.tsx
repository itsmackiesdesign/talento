import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Newspaper, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ImageUpload } from "@/components/image-upload";
import { LanguageTabs, useLanguageTabs, useTranslatedField } from "@/components/lang-tabs";
import { PageHeader } from "@/components/layout";
import { MarkdownField } from "@/components/markdown-field";
import { SortableList, SortableRow } from "@/components/sortable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DrawerContent,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EmptyState, Label, Skeleton, Switch } from "@/components/ui/misc";
import { api } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { formatDate } from "@/lib/utils";

const EMPTY: Partial<NewsItem> = {
  title: "",
  content: "",
  photo_url: "",
  link_url: "",
  is_published: true,
  translations: {},
};

export default function NewsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [editing, setEditing] = useState<Partial<NewsItem> | null>(null);
  const [deleting, setDeleting] = useState<NewsItem | null>(null);

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const news = useQuery({ queryKey: ["news"], queryFn: api.news.list });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["news"] });

  const save = useMutation({
    mutationFn: (item: Partial<NewsItem>) => {
      const payload = {
        title: item.title?.trim(),
        content: item.content ?? "",
        photo_url: item.photo_url?.trim() || null,
        link_url: item.link_url?.trim() || null,
        is_published: item.is_published ?? true,
        translations: item.translations ?? {},
      };
      return item.id ? api.news.update(item.id, payload) : api.news.create(payload);
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: api.news.remove,
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorder = useMutation({
    mutationFn: api.news.reorder,
    onMutate: async (ids) => {
      await qc.cancelQueries({ queryKey: ["news"] });
      const previous = qc.getQueryData<NewsItem[]>(["news"]);
      if (previous) {
        const byId = new Map(previous.map((n) => [n.id, n]));
        qc.setQueryData(["news"], ids.map((id) => byId.get(id)).filter(Boolean) as NewsItem[]);
      }
      return { previous };
    },
    onError: (e: Error, _ids, context) => {
      if (context?.previous) qc.setQueryData(["news"], context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success(t("toast.orderSaved")),
  });

  const list = news.data ?? [];

  return (
    <>
      <PageHeader
        title={t("news.title")}
        description={t("news.subtitle")}
        action={
          <Button onClick={() => setEditing({ ...EMPTY })}>
            <Plus className="h-4 w-4" /> {t("news.add")}
          </Button>
        }
      />

      {news.isPending ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title={t("news.empty")}
          description={t("news.emptyDesc")}
          action={
            <Button onClick={() => setEditing({ ...EMPTY })}>
              <Plus className="h-4 w-4" /> {t("news.add")}
            </Button>
          }
        />
      ) : (
        <SortableList items={list} onReorder={(ids) => reorder.mutate(ids)}>
          {(item) => (
            <SortableRow key={item.id} id={item.id}>
              {item.photo_url && (
                <img
                  src={item.photo_url}
                  alt=""
                  className="h-10 w-10 shrink-0 rounded object-cover"
                  // A dead image URL should not leave a broken-image glyph in the list.
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{item.title}</span>
                  {!item.is_published && (
                    <Badge variant="secondary">{t("news.hidden")}</Badge>
                  )}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {formatDate(item.created_at)}
                  {item.content ? ` · ${item.content}` : ""}
                </p>
              </div>

              <div className="flex shrink-0 gap-1">
                <Button variant="ghost" size="icon" onClick={() => setEditing(item)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setDeleting(item)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </SortableRow>
          )}
        </SortableList>
      )}

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DrawerContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? t("common.edit") : t("news.add")}</DialogTitle>
          </DialogHeader>

          {editing && (
            <NewsForm
              editing={editing}
              setEditing={setEditing}
              enabledLanguages={company.data?.enabled_languages ?? ["ru"]}
              baseLanguage={company.data?.default_language ?? "ru"}
              saving={save.isPending}
              onCancel={() => setEditing(null)}
              onSubmit={() => save.mutate(editing)}
              t={t}
            />
          )}
        </DrawerContent>
      </Dialog>

      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("common.delete")}</DialogTitle>
            <DialogDescription>{deleting?.title}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => deleting && remove.mutate(deleting.id)}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function NewsForm({
  editing,
  setEditing,
  enabledLanguages,
  baseLanguage,
  saving,
  onCancel,
  onSubmit,
  t,
}: {
  editing: Partial<NewsItem>;
  setEditing: (n: Partial<NewsItem>) => void;
  enabledLanguages: string[];
  baseLanguage: string;
  saving: boolean;
  onCancel: () => void;
  onSubmit: () => void;
  t: (key: string) => string;
}) {
  const { ordered, active, setActive } = useLanguageTabs(enabledLanguages, baseLanguage);
  const field = useTranslatedField(editing, setEditing, active, baseLanguage);

  return (
    <form
      className="flex flex-1 flex-col gap-4 overflow-y-auto"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <LanguageTabs
        languages={ordered}
        active={active}
        onChange={setActive}
        base={baseLanguage}
        translations={editing.translations ?? {}}
        fields={["title", "content"]}
      />

      <div className="space-y-2">
        <Label htmlFor="ntitle">{t("news.newsTitle")}</Label>
        <Input
          id="ntitle"
          value={field.value("title")}
          placeholder={field.isBase ? "" : String(editing.title ?? "")}
          onChange={(e) => field.setValue("title", e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="ncontent">{t("news.content")}</Label>
        <MarkdownField
          id="ncontent"
          rows={6}
          value={field.value("content")}
          placeholder={field.isBase ? "" : String(editing.content ?? "")}
          onChange={(v) => field.setValue("content", v)}
        />
      </div>

      {/* Language-independent below. */}
      <ImageUpload
        label={t("news.photoUrl")}
        value={editing.photo_url}
        onChange={(url) => setEditing({ ...editing, photo_url: url })}
      />

      <div className="space-y-2">
        <Label htmlFor="nlink">{t("news.linkUrl")}</Label>
        <Input
          id="nlink"
          value={editing.link_url ?? ""}
          placeholder="https://…"
          onChange={(e) => setEditing({ ...editing, link_url: e.target.value })}
        />
      </div>

      <div className="flex items-center justify-between rounded-lg border p-3">
        <Label htmlFor="npublished">{t("news.published")}</Label>
        <Switch
          id="npublished"
          checked={editing.is_published ?? true}
          onCheckedChange={(checked) => setEditing({ ...editing, is_published: checked })}
        />
      </div>

      <DialogFooter className="mt-auto pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={!editing.title?.trim() || saving}>
          {t("common.save")}
        </Button>
      </DialogFooter>
    </form>
  );
}
