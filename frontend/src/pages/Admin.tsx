import { useState, useEffect } from "react";
import { Shield, Database, Activity, Trash2, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
// (Logs removed) Input/Label/Select related UI removed
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ApiClient, apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";

export default function Admin() {
  const [isAdmin, setIsAdmin] = useState(ApiClient.isAdminMode());
  const [stats, setStats] = useState<any>(null);
  const [dbStatus, setDbStatus] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAdmin(ApiClient.isAdminMode());
    }, 500);
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    setLoading("stats");
    try {
      const result = await apiClient.get("/api/v1/admin/stats");
      setStats(result);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load stats",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const loadDbStatus = async () => {
    setLoading("db");
    try {
      const result = await apiClient.get("/api/v1/admin/database/status");
      setDbStatus(result);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load database status",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const loadHealth = async () => {
    setLoading("health");
    try {
      const result = await apiClient.get("/api/v1/admin/health/detailed");
      setHealth(result);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load health status",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  const clearCache = async () => {
    setLoading("cache");
    try {
      const result = await apiClient.post("/api/v1/admin/cache/clear", {});
      toast({
        title: "Cache cleared",
        description: result.message || `Cleared ${result.items_cleared} items`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to clear cache",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  // logs feature removed

  const loadMetrics = async () => {
    setLoading("metrics");
    try {
      const result = await apiClient.get("/api/v1/admin/metrics");
      setMetrics(result);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load metrics",
        variant: "destructive",
      });
    } finally {
      setLoading(null);
    }
  };

  if (!isAdmin) {
    return (
      <div className="max-w-4xl mx-auto">
        <Alert>
          <Shield className="h-4 w-4" />
          <AlertDescription>
            Admin Tools are disabled. Enable "Admin Mode" in Developer Options to access this page.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Admin Tools</h1>
        <p className="text-muted-foreground">System administration and monitoring</p>
      </div>

      <Alert className="bg-admin-banner border-admin-banner-foreground/20">
        <AlertTriangle className="h-4 w-4 text-admin-banner-foreground" />
        <AlertDescription className="text-admin-banner-foreground">
          Admin Mode is for offline local maintenance only. All operations are performed against your local API.
        </AlertDescription>
      </Alert>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Statistics
            </CardTitle>
            <CardDescription>Overview of system performance</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={loadStats} disabled={loading === "stats"} className="w-full">
              {loading === "stats" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                "Load Statistics"
              )}
            </Button>

            {stats && (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total Queries:</span>
                  <span className="font-medium">{stats.total_queries}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Cache Hit Rate:</span>
                  <span className="font-medium">{(stats.cache_hit_rate * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Processing Time:</span>
                  <span className="font-medium">{stats.average_processing_time.toFixed(3)}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Uptime:</span>
                  <span className="font-medium">{stats.uptime}</span>
                </div>
                {stats.database_status && (
                  <div className="pt-2 border-t">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">DB Status:</span>
                      <Badge variant={stats.database_status.connected ? "default" : "destructive"}>
                        {stats.database_status.connected ? "Connected" : "Disconnected"}
                      </Badge>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-muted-foreground">Total Documents:</span>
                      <span className="font-medium">{stats.database_status.total_documents}</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Database Status
            </CardTitle>
            <CardDescription>Collections and document counts</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={loadDbStatus} disabled={loading === "db"} className="w-full">
              {loading === "db" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                "Load Database Status"
              )}
            </Button>

            {dbStatus && (
              <div className="space-y-2">
                {dbStatus.collections?.map((col: any, idx: number) => (
                  <div key={idx} className="flex justify-between text-sm bg-muted rounded p-2">
                    <span className="font-medium">{col.name}</span>
                    <Badge variant="outline">{col.document_count} docs</Badge>
                  </div>
                ))}
                {dbStatus.total_documents !== undefined && (
                  <div className="flex justify-between pt-2 border-t font-medium">
                    <span>Total:</span>
                    <span>{dbStatus.total_documents}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Detailed Health
            </CardTitle>
            <CardDescription>Component-level health status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={loadHealth} disabled={loading === "health"} className="w-full">
              {loading === "health" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                "Load Health Status"
              )}
            </Button>

            {health && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">Overall:</span>
                  <Badge variant={health.overall_status === "healthy" ? "default" : "destructive"}>
                    {health.overall_status}
                  </Badge>
                </div>
                {Object.entries(health).map(([key, value]: [string, any]) => {
                  if (key === "overall_status" || typeof value !== "object") return null;
                  return (
                    <div key={key} className="bg-muted rounded p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-sm capitalize">{key.replace(/_/g, " ")}</span>
                        <Badge variant={value.status === "healthy" ? "default" : "destructive"} className="text-xs">
                          {value.status}
                        </Badge>
                      </div>
                      {value.details && (
                        <div className="text-xs text-muted-foreground space-y-1">
                          {Object.entries(value.details).map(([k, v]) => (
                            <div key={k}>
                              <span className="font-medium">{k}:</span> {JSON.stringify(v)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5" />
              Cache Management
            </CardTitle>
            <CardDescription>Clear system cache</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={clearCache}
              disabled={loading === "cache"}
              variant="destructive"
              className="w-full"
            >
              {loading === "cache" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Clearing...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Clear Cache
                </>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Recent Logs removed from Admin UI */}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            System Metrics
          </CardTitle>
          <CardDescription>Detailed performance metrics</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={loadMetrics} disabled={loading === "metrics"} className="w-full">
            {loading === "metrics" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </>
            ) : (
              "Load Metrics"
            )}
          </Button>

          {Object.keys(metrics).length > 0 && (
            <div className="space-y-2">
              {Object.entries(metrics).map(([key, value]) => (
                <div key={key} className="bg-muted rounded p-2">
                  <div className="flex items-start justify-between gap-4">
                    <span className="font-medium mr-4 shrink-0">{key}:</span>
                    <div className="flex-1 min-w-0 text-sm">
                      {value && typeof value === "object" && !Array.isArray(value) ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {Object.entries(value).map(([k, v]) => (
                            <div key={k} className="flex justify-between text-xs bg-muted/50 rounded px-2 py-1">
                              <span className="text-muted-foreground mr-2">{k}</span>
                              <span className="font-mono break-words ml-2">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="font-mono break-words">{String(value)}</div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
