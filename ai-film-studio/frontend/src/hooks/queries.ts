import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/services/api";
import type { Category, Scene } from "@/types";

export const keys = {
  dashboard: ["dashboard"] as const,
  activity: ["activity"] as const,
  health: ["health"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  categories: ["categories"] as const,
  topics: (category?: Category) => ["topics", category ?? "all"] as const,
  suggestions: (category: Category) => ["topics", "suggest", category] as const,
  models: ["ai", "models"] as const,
  usage: ["ai", "usage"] as const,
  script: (projectId: string) => ["projects", projectId, "script"] as const,
  storyboard: (projectId: string) => ["projects", projectId, "storyboard"] as const,
  renders: (projectId: string) => ["projects", projectId, "renders"] as const,
  assets: (filters: Record<string, unknown>) => ["assets", filters] as const,
  storageStatus: ["storage", "status"] as const,
  storageGallery: (limit: number) => ["storage", "gallery", limit] as const,
};

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, staleTime: 30_000 });
}

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: api.dashboard });
}

export function useActivity(limit = 50) {
  return useQuery({ queryKey: keys.activity, queryFn: () => api.activity(limit) });
}

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: api.listProjects });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: keys.project(id ?? ""),
    queryFn: () => api.getProject(id as string),
    enabled: Boolean(id),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: api.categories,
    staleTime: 5 * 60_000,
  });
}

export function useTopics(category?: Category) {
  return useQuery({
    queryKey: keys.topics(category),
    queryFn: () => api.listTopics(category),
    enabled: Boolean(category),
  });
}

export function useTopicSuggestions(category: Category | undefined) {
  return useQuery({
    queryKey: keys.suggestions(category ?? "business-tips"),
    queryFn: () => api.suggestTopics(category as Category),
    enabled: Boolean(category),
  });
}

export function useModels() {
  return useQuery({ queryKey: keys.models, queryFn: api.listModels });
}

export function useUsage() {
  return useQuery({ queryKey: keys.usage, queryFn: api.usage });
}

export function useScript(projectId: string | undefined) {
  return useQuery({
    queryKey: keys.script(projectId ?? ""),
    queryFn: () => api.getScript(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useStoryboard(projectId: string | undefined) {
  return useQuery({
    queryKey: keys.storyboard(projectId ?? ""),
    queryFn: () => api.getStoryboard(projectId as string),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useRenders(projectId: string | undefined) {
  return useQuery({
    queryKey: keys.renders(projectId ?? ""),
    queryFn: () => api.listRenders(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      if (!jobs) return false;
      return jobs.some((job) => job.status === "queued" || job.status === "running")
        ? 2000
        : false;
    },
  });
}

export function useRenderLogs(jobId: string | undefined, active: boolean) {
  return useQuery({
    queryKey: ["renders", jobId, "logs"],
    queryFn: () => api.getRenderLogs(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: active ? 2000 : false,
  });
}

export function useAssets(filters: {
  search?: string;
  media_type?: string;
  tag?: string;
  favorite?: boolean;
}) {
  return useQuery({
    queryKey: keys.assets(filters),
    queryFn: () => api.listAssets(filters),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return (...queryKeys: (readonly unknown[])[]) => {
    for (const queryKey of queryKeys) {
      void queryClient.invalidateQueries({ queryKey });
    }
  };
}

export function useCreateProject() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.createProject,
    onSuccess: () => invalidate(keys.projects, keys.dashboard),
  });
}

export function useUpdateProject() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof api.updateProject>[1] }) =>
      api.updateProject(id, payload),
    onSuccess: (project) =>
      invalidate(keys.projects, keys.project(project.id), keys.dashboard),
  });
}

export function useDeleteProject() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.deleteProject,
    onSuccess: () => invalidate(keys.projects, keys.dashboard),
  });
}

export function useUpdateProgress(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.updateProgress>[1]) =>
      api.updateProgress(projectId, payload),
    onSuccess: () => invalidate(keys.project(projectId), keys.projects, keys.dashboard),
  });
}

export function useGenerateScript(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.generateScript>[1]) =>
      api.generateScript(projectId, payload),
    onSuccess: () =>
      invalidate(keys.script(projectId), keys.project(projectId), keys.dashboard),
  });
}

export function useUpdateScript(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (content: string) => api.updateScript(projectId, content),
    onSuccess: () => invalidate(keys.script(projectId), keys.project(projectId)),
  });
}

export function useRegenerateParagraph(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ index, instruction }: { index: number; instruction?: string }) =>
      api.regenerateParagraph(projectId, index, instruction),
    onSuccess: () => invalidate(keys.script(projectId), keys.project(projectId)),
  });
}

export function useApproveScript(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (approved: boolean) => api.approveScript(projectId, approved),
    onSuccess: () => invalidate(keys.script(projectId), keys.project(projectId), keys.dashboard),
  });
}

export function useGenerateStoryboard(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.generateStoryboard>[1]) =>
      api.generateStoryboard(projectId, payload),
    onSuccess: () =>
      invalidate(keys.storyboard(projectId), keys.project(projectId), keys.dashboard),
  });
}

export function useUpdateScene(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ sceneId, payload }: { sceneId: string; payload: Partial<Scene> }) =>
      api.updateScene(projectId, sceneId, payload),
    onSuccess: () => invalidate(keys.storyboard(projectId), keys.project(projectId)),
  });
}

export function useReorderScenes(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (scenes: { id: string; order_index: number }[]) =>
      api.reorderScenes(projectId, scenes),
    onSuccess: () => invalidate(keys.storyboard(projectId), keys.project(projectId)),
  });
}

export function useRegenerateScene(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ sceneId, instruction }: { sceneId: string; instruction?: string }) =>
      api.regenerateScene(projectId, sceneId, instruction),
    onSuccess: () => invalidate(keys.storyboard(projectId), keys.project(projectId)),
  });
}

export function useApproveStoryboard(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (approved: boolean) => api.approveStoryboard(projectId, approved),
    onSuccess: () =>
      invalidate(keys.storyboard(projectId), keys.project(projectId), keys.dashboard),
  });
}

export function useSelectModel() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.selectModel,
    onSuccess: () => invalidate(keys.models, keys.usage, keys.dashboard),
  });
}

export function useTestModel() {
  return useMutation({ mutationFn: api.testModel });
}

export function useGenerateAI() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.generateAI,
    onSuccess: () => invalidate(keys.usage, keys.dashboard),
  });
}

export function useCreateRender(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.createRender>[1]) =>
      api.createRender(projectId, payload),
    onSuccess: () =>
      invalidate(keys.renders(projectId), keys.project(projectId), keys.dashboard),
  });
}

export function useCancelRender(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.cancelRender,
    onSuccess: () => invalidate(keys.renders(projectId), keys.project(projectId)),
  });
}

export function useStorageStatus() {
  return useQuery({
    queryKey: keys.storageStatus,
    queryFn: () => api.storageStatus(),
    staleTime: 60_000,
  });
}

export function useStorageGallery(limit = 24, enabled = true) {
  return useQuery({
    queryKey: keys.storageGallery(limit),
    queryFn: () => api.storageGallery(limit),
    staleTime: 30_000,
    enabled,
  });
}

export function usePublishRender(projectId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.publishRender,
    onSuccess: () =>
      invalidate(
        keys.renders(projectId),
        keys.project(projectId),
        keys.storageStatus,
        keys.storageGallery(24),
        keys.dashboard,
      ),
  });
}

export function useUploadAsset() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ file, tags }: { file: File; tags?: string }) =>
      api.uploadAsset(file, tags),
    onSuccess: () => invalidate(["assets"], keys.dashboard),
  });
}

export function useUpdateAsset() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { tags?: string[]; favorite?: boolean } }) =>
      api.updateAsset(id, payload),
    onSuccess: () => invalidate(["assets"]),
  });
}

export function useDeleteAsset() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: api.deleteAsset,
    onSuccess: () => invalidate(["assets"], keys.dashboard),
  });
}
