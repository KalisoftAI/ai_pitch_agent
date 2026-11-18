import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { ProjectLayout } from "@/components/layout/project-layout";
import { AssetsPage } from "@/pages/assets";
import { AIUsagePage } from "@/pages/ai-usage";
import { DashboardPage } from "@/pages/dashboard";
import { ProjectOverviewPage } from "@/pages/project-overview";
import { ProjectsPage } from "@/pages/projects";
import { RenderPage } from "@/pages/render";
import { ScriptPage } from "@/pages/script";
import { SettingsPage } from "@/pages/settings";
import { StoryboardPage } from "@/pages/storyboard";
import { WizardPage } from "@/pages/wizard";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="create" element={<WizardPage />} />
        <Route path="projects/:id" element={<ProjectLayout />}>
          <Route index element={<ProjectOverviewPage />} />
          <Route path="script" element={<ScriptPage />} />
          <Route path="storyboard" element={<StoryboardPage />} />
          <Route path="render" element={<RenderPage />} />
        </Route>
        <Route path="assets" element={<AssetsPage />} />
        <Route path="ai" element={<AIUsagePage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
