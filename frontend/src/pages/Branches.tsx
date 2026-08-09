import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Copy, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ImageUpload } from "@/components/image-upload";
import { LanguageTabs, useLanguageTabs, useTranslatedField } from "@/components/lang-tabs";
import { PageHeader } from "@/components/layout";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Branch, Bot } from "@/lib/types";

const EMPTY: Partial<Branch> = {
  name: "",
  city: "",
  address: "",
  photo_url: "",
  latitude: null,
  longitude: null,
  is_active: true,
};

export default function BranchesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [editing, setEditing] = useState<Partial<Branch> | null>(null);
  const [deleting, setDeleting] = useState<Branch | null>(null);
  const [moveTarget, setMoveTarget] = useState<string>("null");

  const company = useQuery({ queryKey: ["company"], queryFn: api.company.get });
  const branches = useQuery({ queryKey: ["branches"], queryFn: api.branches.list });
  const bot = useQuery<Bot | null>({
    queryKey: ["bot"],
    queryFn: () => api.bot.get().catch(() => null),
    retry: false,
  });

  const invalidate = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["branches"] }),
      qc.invalidateQueries({ queryKey: ["me"] }),
      qc.invalidateQueries({ queryKey: ["vacancies"] }),
    ]);

  const save = useMutation({
    mutationFn: (branch: Partial<Branch>) => {
      const payload = {
        name: branch.name?.trim(),
        city: branch.city?.trim() || null,
        address: branch.address?.trim() || null,
        is_active: branch.is_active,
        photo_url: branch.photo_url?.trim() || null,
        latitude: branch.latitude ?? null,
        longitude: branch.longitude ?? null,
        translations: branch.translations ?? {},
      };
      return branch.id
        ? api.branches.update(branch.id, payload)
        : api.branches.create(payload);
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
      toast.success(t("toast.saved"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: ({ id, moveTo }: { id: string; moveTo: string }) =>
      api.branches.remove(id, moveTo === "null" ? null : moveTo),
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
      setMoveTarget("null");
      toast.success(t("toast.deleted"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorder = useMutation({
    mutationFn: api.branches.reorder,
    onMutate: async (ids) => {
      // Optimistic: reflect the drop instantly, roll back if the request fails.
      await qc.cancelQueries({ queryKey: ["branches"] });
      const previous = qc.getQueryData<Branch[]>(["branches"]);
      if (previous) {
        const byId = new Map(previous.map((b) => [b.id, b]));
        qc.setQueryData(
          ["branches"],
          ids.map((id) => byId.get(id)).filter(Boolean) as Branch[],
        );
      }
      return { previous };
    },
    onError: (e: Error, _ids, context) => {
      if (context?.previous) qc.setQueryData(["branches"], context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success(t("toast.orderSaved")),
  });

  const list = branches.data ?? [];

  return (
    <>
      <PageHeader
        title={t("branches.title")}
        description={t("branches.subtitle")}
        action={
          <Button onClick={() => setEditing({ ...EMPTY })}>
            <Plus className="h-4 w-4" /> {t("branches.add")}
          </Button>
        }
      />

      {branches.isPending ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <EmptyState
          icon={Building2}
          title={t("branches.empty")}
          description={t("branches.emptyDesc")}
          action={
            <Button onClick={() => setEditing({ ...EMPTY })}>
              <Plus className="h-4 w-4" /> {t("branches.add")}
            </Button>
          }
        />
      ) : (
        <SortableList items={list} onReorder={(ids) => reorder.mutate(ids)}>
          {(branch) => (
            <SortableRow key={branch.id} id={branch.id}>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{branch.name}</span>
                  {!branch.is_active && <Badge variant="secondary">{t("branches.hidden")}</Badge>}
                  <Badge variant="outline">
                    {t("branches.vacancyCount")}: {branch.active_vacancy_count}
                  </Badge>
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {[branch.city, branch.address].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>

              <div className="flex shrink-0 gap-1">
                {bot.data && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title={t("branches.deepLink")}
                    onClick={() => {
                      const link = `https://t.me/${bot.data!.bot_username}?start=branch_${branch.id.replaceAll("-", "")}`;
                      navigator.clipboard.writeText(link);
                      toast.success(t("toast.linkCopied"));
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={() => setEditing(branch)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setDeleting(branch)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </SortableRow>
          )}
        </SortableList>
      )}

      {/* Create / edit drawer */}
      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DrawerContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? t("common.edit") : t("branches.add")}</DialogTitle>
          </DialogHeader>

          {editing && (
            <BranchForm
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

      {/* Delete dialog — always asks what to do with the branch's vacancies. */}
      <Dialog open={Boolean(deleting)} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("branches.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("branches.deleteDesc")}</DialogDescription>
          </DialogHeader>

          <Select value={moveTarget} onValueChange={setMoveTarget}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="null">{t("branches.detach")}</SelectItem>
              {list
                .filter((b) => b.id !== deleting?.id)
                .map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {t("branches.moveTo")}: {b.name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleting(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => deleting && remove.mutate({ id: deleting.id, moveTo: moveTarget })}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}


function BranchForm({
  editing,
  setEditing,
  enabledLanguages,
  baseLanguage,
  saving,
  onCancel,
  onSubmit,
  t,
}: {
  editing: Partial<Branch>;
  setEditing: (b: Partial<Branch>) => void;
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
      className="flex flex-1 flex-col gap-4"
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
        fields={["name", "city", "address"]}
      />

      <div className="space-y-2">
        <Label htmlFor="name">{t("branches.name")}</Label>
        <Input
          id="name"
          value={field.value("name")}
          placeholder={field.isBase ? "Филиал Чиланзар" : String(editing.name ?? "")}
          onChange={(e) => field.setValue("name", e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="city">{t("branches.city")}</Label>
        <Input
          id="city"
          value={field.value("city")}
          placeholder={field.isBase ? "Ташкент" : String(editing.city ?? "")}
          onChange={(e) => field.setValue("city", e.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="address">{t("branches.address")}</Label>
        <Input
          id="address"
          value={field.value("address")}
          placeholder={field.isBase ? "" : String(editing.address ?? "")}
          onChange={(e) => field.setValue("address", e.target.value)}
        />
      </div>

      <ImageUpload
        label={t("branches.photoUrl")}
        value={editing.photo_url}
        onChange={(url) => setEditing({ ...editing, photo_url: url })}
      />

      {/* The API requires both coordinates or neither, so an empty box clears the pair. */}
      <div className="space-y-2">
        <Label>{t("branches.geoHint")}</Label>
        <div className="grid grid-cols-2 gap-4">
          <Input
            aria-label={t("branches.latitude")}
            type="number"
            step="any"
            placeholder={t("branches.latitude")}
            value={editing.latitude ?? ""}
            onChange={(e) =>
              setEditing({
                ...editing,
                latitude: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
          <Input
            aria-label={t("branches.longitude")}
            type="number"
            step="any"
            placeholder={t("branches.longitude")}
            value={editing.longitude ?? ""}
            onChange={(e) =>
              setEditing({
                ...editing,
                longitude: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </div>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-3">
        <Label htmlFor="active">{t("branches.active")}</Label>
        <Switch
          id="active"
          checked={editing.is_active ?? true}
          onCheckedChange={(checked) => setEditing({ ...editing, is_active: checked })}
        />
      </div>

      <DialogFooter className="mt-auto pt-4">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button type="submit" disabled={!editing.name?.trim() || saving}>
          {t("common.save")}
        </Button>
      </DialogFooter>
    </form>
  );
}
