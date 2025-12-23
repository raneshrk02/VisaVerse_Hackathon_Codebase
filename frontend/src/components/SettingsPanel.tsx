import { ReactNode, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { toast } from "@/hooks/use-toast";

interface SettingsPanelProps {
  children: ReactNode;
}

export function SettingsPanel({ children }: SettingsPanelProps) {
  const [baseUrl, setBaseUrl] = useState(apiClient.getBaseUrl());
  const [open, setOpen] = useState(false);

  const handleSave = () => {
    try {
      new URL(baseUrl); // Validate URL
      apiClient.setBaseUrl(baseUrl);
      toast({
        title: "Settings saved",
        description: "API base URL updated successfully",
      });
      setOpen(false);
    } catch (error) {
      toast({
        title: "Invalid URL",
        description: "Please enter a valid URL",
        variant: "destructive",
      });
    }
  };

  const handleReset = () => {
    setBaseUrl("http://localhost:8001");
    apiClient.setBaseUrl("http://localhost:8001");
    toast({
      title: "Reset to default",
      description: "API base URL reset to http://localhost:8001",
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Configure the API base URL for all requests
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="base-url">API Base URL</Label>
            <Input
              id="base-url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:8001"
            />
            <p className="text-xs text-muted-foreground">
              Default: http://localhost:8001
            </p>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSave} className="flex-1">
              Save
            </Button>
            <Button variant="outline" onClick={handleReset}>
              Reset to Default
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
