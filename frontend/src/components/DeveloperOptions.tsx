import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiClient } from "@/lib/api-client";

export function DeveloperOptions() {
  const [isOpen, setIsOpen] = useState(false);
  const [adminMode, setAdminMode] = useState(ApiClient.isAdminMode());

  const handleAdminToggle = (checked: boolean) => {
    ApiClient.setAdminMode(checked);
    setAdminMode(checked);
  };

  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader className="cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm font-medium">Developer Options</CardTitle>
            <CardDescription className="text-xs">
              Local development settings
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>

      {isOpen && (
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="admin-mode">Enable Admin Mode (local use only)</Label>
              <p className="text-xs text-muted-foreground">
                Sets X-User-Role header to "admin" for all requests
              </p>
            </div>
            <Switch
              id="admin-mode"
              checked={adminMode}
              onCheckedChange={handleAdminToggle}
            />
          </div>
        </CardContent>
      )}
    </Card>
  );
}
