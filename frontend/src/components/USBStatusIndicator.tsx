/**
 * USB Status Indicator Component
 * 
 * Shows the current status of the USB deployment including backend connectivity
 */

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from '@/components/ui/tooltip';
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { 
  Usb, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  AlertCircle,
  CheckCircle,
  Settings
} from 'lucide-react';
import { BackendDiscoveryService } from '@/lib/backend-discovery';
import { apiClient } from '@/lib/api-client';
import { usbConfig } from '@/config/usb-config';

interface BackendStatus {
  connected: boolean;
  url: string;
  responseTime?: number;
  lastChecked: Date;
  error?: string;
}

export const USBStatusIndicator: React.FC = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({
    connected: false,
    url: 'Unknown',
    lastChecked: new Date(),
  });
  const [isChecking, setIsChecking] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  // Check backend status
  const checkBackendStatus = async () => {
    setIsChecking(true);
    try {
      const startTime = Date.now();
      
      // Try a simple health check
      await apiClient.get('/health');
      
      const responseTime = Date.now() - startTime;
      setBackendStatus({
        connected: true,
        url: apiClient.getBaseUrl(),
        responseTime,
        lastChecked: new Date(),
      });
    } catch (error) {
      setBackendStatus({
        connected: false,
        url: apiClient.getBaseUrl(),
        lastChecked: new Date(),
        error: error instanceof Error ? error.message : 'Connection failed',
      });
    } finally {
      setIsChecking(false);
    }
  };

  // Rediscover backend
  const rediscoverBackend = async () => {
    setIsChecking(true);
    try {
      const discovery = await BackendDiscoveryService.discoverBackend();
      
      if (discovery.success && discovery.backend) {
        apiClient.setBaseUrl(discovery.backend.url);
        setBackendStatus({
          connected: true,
          url: discovery.backend.url,
          lastChecked: new Date(),
        });
      } else {
        setBackendStatus({
          connected: false,
          url: apiClient.getBaseUrl(),
          lastChecked: new Date(),
          error: discovery.error || 'Discovery failed',
        });
      }
    } catch (error) {
      setBackendStatus({
        connected: false,
        url: apiClient.getBaseUrl(),
        lastChecked: new Date(),
        error: error instanceof Error ? error.message : 'Discovery failed',
      });
    } finally {
      setIsChecking(false);
    }
  };

  // Initial check and periodic updates
  useEffect(() => {
    if (usbConfig.ui.showBackendStatus) {
      checkBackendStatus();
      
      // Check every 30 seconds
      const interval = setInterval(checkBackendStatus, 30000);
      return () => clearInterval(interval);
    }
  }, []);

  // Don't render if not in USB mode or disabled
  if (!usbConfig.ui.showUSBIndicator) {
    return null;
  }

  const getStatusColor = () => {
    if (isChecking) return 'bg-yellow-500';
    return backendStatus.connected ? 'bg-green-500' : 'bg-red-500';
  };

  const getStatusText = () => {
    if (isChecking) return 'Checking...';
    return backendStatus.connected ? 'Connected' : 'Disconnected';
  };

  const getStatusIcon = () => {
    if (isChecking) return <RefreshCw className="h-3 w-3 animate-spin" />;
    return backendStatus.connected ? 
      <CheckCircle className="h-3 w-3" /> : 
      <AlertCircle className="h-3 w-3" />;
  };

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <TooltipProvider>
        <div className="flex items-center gap-2">
          {/* USB Indicator */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="flex items-center gap-1">
                <Usb className="h-3 w-3" />
                <span className="text-xs">USB</span>
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <p>Running in USB portable mode</p>
            </TooltipContent>
          </Tooltip>

          {/* Backend Status */}
          {usbConfig.ui.showBackendStatus && (
            <Dialog open={showDetails} onOpenChange={setShowDetails}>
              <DialogTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-2 h-6 px-2"
                >
                  <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
                  {getStatusIcon()}
                  <span className="text-xs">{getStatusText()}</span>
                </Button>
              </DialogTrigger>
              
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    Backend Connection Status
                  </DialogTitle>
                  <DialogDescription>
                    Current status of the SAGE backend connection
                  </DialogDescription>
                </DialogHeader>
                
                <div className="space-y-4">
                  {/* Connection Status */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Status:</span>
                    <Badge variant={backendStatus.connected ? "default" : "destructive"}>
                      {getStatusText()}
                    </Badge>
                  </div>

                  {/* Backend URL */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Backend URL:</span>
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {backendStatus.url}
                    </code>
                  </div>

                  {/* Response Time */}
                  {backendStatus.responseTime && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Response Time:</span>
                      <span className="text-sm text-muted-foreground">
                        {backendStatus.responseTime}ms
                      </span>
                    </div>
                  )}

                  {/* Last Checked */}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Last Checked:</span>
                    <span className="text-sm text-muted-foreground">
                      {backendStatus.lastChecked.toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Error Message */}
                  {backendStatus.error && (
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-destructive">Error:</span>
                      <p className="text-xs text-muted-foreground bg-muted p-2 rounded">
                        {backendStatus.error}
                      </p>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-2 pt-4">
                    <Button
                      onClick={checkBackendStatus}
                      disabled={isChecking}
                      size="sm"
                      variant="outline"
                      className="flex-1"
                    >
                      {isChecking ? (
                        <RefreshCw className="h-3 w-3 animate-spin mr-2" />
                      ) : (
                        <Wifi className="h-3 w-3 mr-2" />
                      )}
                      Check Status
                    </Button>
                    
                    <Button
                      onClick={rediscoverBackend}
                      disabled={isChecking}
                      size="sm"
                      className="flex-1"
                    >
                      {isChecking ? (
                        <RefreshCw className="h-3 w-3 animate-spin mr-2" />
                      ) : (
                        <WifiOff className="h-3 w-3 mr-2" />
                      )}
                      Rediscover
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </TooltipProvider>
    </div>
  );
};