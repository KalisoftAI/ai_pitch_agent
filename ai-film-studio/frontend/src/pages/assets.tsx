import {
  FileVideo,
  Heart,
  Image as ImageIcon,
  Search,
  Star,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/progress";
import { Segmented } from "@/components/ui/segmented";
import {
  useAssets,
  useDeleteAsset,
  useUpdateAsset,
  useUploadAsset,
} from "@/hooks/queries";
import { api } from "@/services/api";
import { cn, formatBytes, formatRelative } from "@/lib/utils";
import { toast } from "@/stores/ui";
import type { Asset } from "@/types";

type Filter = "all" | "image" | "video" | "favorite";

export function AssetsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<Asset | null>(null);
  const [tagDraft, setTagDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: assets, isLoading } = useAssets({
    search: search || undefined,
    favorite: filter === "favorite" ? true : undefined,
    media_type: filter === "image" || filter === "video" ? filter : undefined,
  });
  const upload = useUploadAsset();
  const updateAsset = useUpdateAsset();
  const deleteAsset = useDeleteAsset();

  const totalSize = useMemo(
    () => (assets ?? []).reduce((sum, asset) => sum + asset.size_bytes, 0),
    [assets],
  );

  const uploadFiles = (files: FileList | File[]) => {
    const list = Array.from(files);
    for (const file of list) {
      upload.mutate(
        { file },
        {
          onSuccess: () => toast.success(`${file.name} uploaded`),
          onError: (error) => toast.error(`Could not upload ${file.name}`, error.message),
        },
      );
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Library"
        title="Assets"
        description="Reference images, product shots, and clips available to the storyboard."
        actions={
          <Button onClick={() => inputRef.current?.click()} loading={upload.isPending}>
            <UploadCloud className="h-4 w-4" /> Upload asset
          </Button>
        }
      />

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Segmented
          className="max-w-xl"
          value={filter}
          onChange={setFilter}
          items={[
            { value: "all", label: "All" },
            { value: "image", label: "Images", icon: ImageIcon },
            { value: "video", label: "Videos", icon: FileVideo },
            { value: "favorite", label: "Favorites", icon: Heart },
          ]}
        />
        <div className="relative w-full lg:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search assets..."
            className="pl-9"
          />
        </div>
      </div>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          if (event.dataTransfer.files.length) uploadFiles(event.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer items-center justify-center gap-3 rounded-2xl border border-dashed p-6 text-sm transition",
          dragOver
            ? "border-primary/60 bg-primary/10 text-primary"
            : "border-border/80 bg-card/30 text-muted-foreground hover:border-primary/40 hover:bg-card/60",
        )}
      >
        <UploadCloud className="h-5 w-5" />
        Drop files here or click to upload
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/*,video/*"
          className="hidden"
          onChange={(event) => {
            if (event.target.files) uploadFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {assets?.length ?? 0} assets · {formatBytes(totalSize)}
        </span>
        <span>Images and MP4 clips, up to 100 MB each</span>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-56" />
          ))}
        </div>
      ) : (assets ?? []).length === 0 ? (
        <EmptyState
          icon={ImageIcon}
          title="No assets yet"
          description="Upload product screenshots, brand images, or reference clips. They stay in local storage."
          action={
            <Button onClick={() => inputRef.current?.click()}>
              <UploadCloud className="h-4 w-4" /> Upload your first asset
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {(assets ?? []).map((asset) => (
            <Card key={asset.id} className="panel-hover group overflow-hidden">
              <button
                className="relative block aspect-video w-full overflow-hidden bg-black/40"
                onClick={() => {
                  setPreview(asset);
                  setTagDraft(asset.tags.join(", "));
                }}
              >
                {asset.media_type === "image" ? (
                  <img
                    src={api.assetFileUrl(asset)}
                    alt={asset.original_name}
                    className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <FileVideo className="h-8 w-8 text-muted-foreground/60" />
                  </div>
                )}
                {asset.favorite ? (
                  <span className="absolute left-2 top-2 rounded-full bg-black/60 p-1 text-warning">
                    <Star className="h-3.5 w-3.5 fill-current" />
                  </span>
                ) : null}
              </button>
              <CardContent className="space-y-2 p-3">
                <p className="truncate text-sm font-medium" title={asset.original_name}>
                  {asset.original_name}
                </p>
                <div className="flex flex-wrap gap-1">
                  {(asset.tags.length ? asset.tags : [asset.media_type]).slice(0, 3).map((tag) => (
                    <Badge key={tag} variant="default">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{formatBytes(asset.size_bytes)}</span>
                  <span>{formatRelative(asset.created_at)}</span>
                </div>
                <div className="flex gap-1 pt-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="flex-1"
                    onClick={() =>
                      updateAsset.mutate(
                        { id: asset.id, payload: { favorite: !asset.favorite } },
                        {
                          onError: (error) => toast.error("Could not update", error.message),
                        },
                      )
                    }
                  >
                    <Star className={cn("h-3.5 w-3.5", asset.favorite && "fill-current text-warning")} />
                    {asset.favorite ? "Saved" : "Save"}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => {
                      deleteAsset.mutate(asset.id, {
                        onSuccess: () => toast.success("Asset deleted"),
                        onError: (error) => toast.error("Delete failed", error.message),
                      });
                    }}
                    aria-label="Delete asset"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-danger" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={Boolean(preview)}
        onClose={() => setPreview(null)}
        title={preview?.original_name ?? "Asset"}
        description={preview ? `${formatBytes(preview.size_bytes)} · ${preview.content_type}` : undefined}
        className="max-w-2xl"
        footer={
          preview ? (
            <>
              <Button variant="ghost" onClick={() => setPreview(null)}>
                Close
              </Button>
              <Button
                loading={updateAsset.isPending}
                onClick={() => {
                  updateAsset.mutate(
                    {
                      id: preview.id,
                      payload: {
                        tags: tagDraft
                          .split(",")
                          .map((tag) => tag.trim())
                          .filter(Boolean),
                      },
                    },
                    {
                      onSuccess: () => {
                        toast.success("Asset updated");
                        setPreview(null);
                      },
                      onError: (error) => toast.error("Could not update", error.message),
                    },
                  );
                }}
              >
                Save tags
              </Button>
            </>
          ) : null
        }
      >
        {preview ? (
          <div className="space-y-4">
            {preview.media_type === "image" ? (
              <img
                src={api.assetFileUrl(preview)}
                alt={preview.original_name}
                className="max-h-[46vh] w-full rounded-xl border border-border object-contain"
              />
            ) : (
              <video
                src={api.assetFileUrl(preview)}
                controls
                className="max-h-[46vh] w-full rounded-xl border border-border"
              />
            )}
            <div>
              <Label htmlFor="asset-tags">Tags (comma separated)</Label>
              <Input
                id="asset-tags"
                value={tagDraft}
                onChange={(event) => setTagDraft(event.target.value)}
                placeholder="product, dashboard, finance"
              />
            </div>
            <Button asChild variant="secondary" size="sm">
              <a href={api.assetFileUrl(preview)} target="_blank" rel="noreferrer">
                Open original
              </a>
            </Button>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
