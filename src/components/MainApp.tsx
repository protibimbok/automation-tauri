import { Navigate, Route, Routes } from "react-router-dom";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { getRoutes } from "@/lib/modular";

export function MainApp() {
  const moduleRoutes = getRoutes();

  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        {moduleRoutes.map((route) => (
          <Route
            key={route.path ?? (route.index ? "index" : "route")}
            index={route.index}
            path={route.path}
            element={route.element}
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
