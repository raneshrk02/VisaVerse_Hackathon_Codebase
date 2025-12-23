import { useState } from "react";
import { Activity, CheckCircle, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";

interface HealthStatus {
  status: string;
  version?: string;
  timestamp?: string;
}

export default function Status() {
  const [basicHealth, setBasicHealth] = useState<HealthStatus | null>(null);
  const [readyHealth, setReadyHealth] = useState<HealthStatus | null>(null);
  const [liveHealth, setLiveHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const checkHealth = async (endpoint: string, setter: (data: HealthStatus) => void) => {
    setLoading(endpoint);
    try {
      const result = await apiClient.get<HealthStatus>(`/api/v1/health${endpoint}`);
      setter(result);
      toast({
        title: "Health check complete",
        description: `Status: ${result.status}`,
      });
    } catch (error) {
      toast({
        title: "Health check failed",
        description: error instanceof Error ? error.message : "Unable to reach endpoint",
        variant: "destructive",
      });
      setter({ status: "error" });
    } finally {
      setLoading(null);
    }
  };

  const getStatusIcon = (status: string | undefined) => {
    const s = (status || "").toLowerCase();
    if (["healthy", "ok", "ready", "alive"].includes(s)) {
      return <CheckCircle className="h-5 w-5 text-success" />;
    }
    if (["error", "unhealthy", "not_ready"].includes(s)) {
      return <XCircle className="h-5 w-5 text-destructive" />;
    }
    return <AlertCircle className="h-5 w-5 text-warning" />;
  };

  const getStatusBadge = (status: string | undefined) => {
    const s = (status || "").toLowerCase();
    if (["healthy", "ok", "ready", "alive"].includes(s)) {
      return <Badge className="bg-success text-success-foreground">Healthy</Badge>;
    }
    if (["error", "unhealthy", "not_ready"].includes(s)) {
      return <Badge variant="destructive">Error</Badge>;
    }
    return <Badge variant="secondary">Unknown</Badge>;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Status</h1>
        <p className="text-muted-foreground">Monitor API health and availability</p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Basic Health Check
            </CardTitle>
            <CardDescription>
              GET /api/v1/health/ - General health status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              onClick={() => checkHealth("/", setBasicHealth)}
              disabled={loading === "/"}
              className="w-full"
            >
              {loading === "/" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking...
                </>
              ) : (
                "Check Health"
              )}
            </Button>

            {basicHealth && (
              <div className="space-y-3 bg-muted rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(basicHealth.status)}
                    <span className="font-medium">Status</span>
                  </div>
                  {getStatusBadge(basicHealth.status)}
                </div>

                {basicHealth.version && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Version:</span>
                    <span className="font-mono">{basicHealth.version}</span>
                  </div>
                )}

                {basicHealth.timestamp && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Timestamp:</span>
                    <span className="font-mono">{basicHealth.timestamp}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              Readiness Check
            </CardTitle>
            <CardDescription>
              GET /api/v1/health/ready - Service readiness status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              onClick={() => checkHealth("/ready", setReadyHealth)}
              disabled={loading === "/ready"}
              className="w-full"
            >
              {loading === "/ready" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking...
                </>
              ) : (
                "Check Readiness"
              )}
            </Button>

            {readyHealth && (
              <div className="space-y-3 bg-muted rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(readyHealth.status)}
                    <span className="font-medium">Status</span>
                  </div>
                  {getStatusBadge(readyHealth.status)}
                </div>

                {readyHealth.version && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Version:</span>
                    <span className="font-mono">{readyHealth.version}</span>
                  </div>
                )}

                {readyHealth.timestamp && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Timestamp:</span>
                    <span className="font-mono">{readyHealth.timestamp}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Liveness Check
            </CardTitle>
            <CardDescription>
              GET /api/v1/health/live - Service liveness status
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button
              onClick={() => checkHealth("/live", setLiveHealth)}
              disabled={loading === "/live"}
              className="w-full"
            >
              {loading === "/live" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Checking...
                </>
              ) : (
                "Check Liveness"
              )}
            </Button>

            {liveHealth && (
              <div className="space-y-3 bg-muted rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(liveHealth.status)}
                    <span className="font-medium">Status</span>
                  </div>
                  {getStatusBadge(liveHealth.status)}
                </div>

                {liveHealth.version && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Version:</span>
                    <span className="font-mono">{liveHealth.version}</span>
                  </div>
                )}

                {liveHealth.timestamp && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Timestamp:</span>
                    <span className="font-mono">{liveHealth.timestamp}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="text-base">About Health Checks</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            <strong>Basic Health:</strong> General system health and availability
          </p>
          <p>
            <strong>Readiness:</strong> Whether the service is ready to accept requests
          </p>
          <p>
            <strong>Liveness:</strong> Whether the service is running and responsive
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
