import type { Plugin } from "vite";

export const isResearchReadRoute = (url: string) => /^\/api\/v1\/boats(?:\/|\?|$)/.test(url);

/** Local research reads only. Message ingestion is never exposed by this proxy. */
export function researchApiProxy(): Plugin {
  let research = false;
  return {
    name: "research-read-only-fms-api",
    apply: "serve",
    config(_config, environment) {
      research = environment.mode === "research";
      if (!research) return;
      return {
        server: {
          proxy: {
            "^/api/v1/boats(?:/|\\?|$)": { target: "http://127.0.0.1:8765", changeOrigin: false },
          },
        },
      };
    },
    configureServer(server) {
      if (!research) return;
      server.middlewares.use((request, response, next) => {
        if (isResearchReadRoute(request.url ?? "") && request.method !== "GET") {
          response.statusCode = 405;
          response.setHeader("Allow", "GET");
          response.setHeader("Content-Type", "application/json");
          response.end(JSON.stringify({ error: "The research dashboard proxy permits GET only" }));
          return;
        }
        next();
      });
    },
  };
}
