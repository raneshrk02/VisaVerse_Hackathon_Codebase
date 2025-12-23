/**
 * USB Deployment Configuration
 * 
 * This file contains configuration specific to USB portable deployment
 */

export interface USBConfig {
  // Backend discovery settings
  backendDiscovery: {
    enabled: boolean;
    commonPorts: number[];
    discoveryTimeout: number;
    maxConcurrentAttempts: number;
    cacheTimeout: number;
  };

  // Performance settings
  performance: {
    enableCompression: boolean;
    enableCaching: boolean;
    chunkSizeWarningLimit: number;
    requestTimeout: number;
  };

  // Feature flags
  features: {
    enableAdminMode: boolean;
    enableDeveloperOptions: boolean;
    enableAnalytics: boolean;
    enableServiceWorker: boolean;
  };

  // UI settings
  ui: {
    showUSBIndicator: boolean;
    showBackendStatus: boolean;
    autoOpenBrowser: boolean;
  };
}

// Default USB configuration
export const defaultUSBConfig: USBConfig = {
  backendDiscovery: {
    enabled: true,
    commonPorts: [8001],
    discoveryTimeout: 5000,
    maxConcurrentAttempts: 3,
    cacheTimeout: 5 * 60 * 1000, // 5 minutes
  },

  performance: {
    enableCompression: true,
    enableCaching: true,
    chunkSizeWarningLimit: 1000,
    requestTimeout: 30000,
  },

  features: {
    enableAdminMode: true,
    enableDeveloperOptions: false,
    enableAnalytics: false,
    enableServiceWorker: false,
  },

  ui: {
    showUSBIndicator: true,
    showBackendStatus: true,
    autoOpenBrowser: true,
  },
};

// Environment-based configuration
export const getUSBConfig = (): USBConfig => {
  const isUSBDeployment = import.meta.env.VITE_USB_DEPLOYMENT === "true";
  const isDevelopment = import.meta.env.DEV;

  if (!isUSBDeployment) {
    // Return minimal config for non-USB deployment
    return {
      ...defaultUSBConfig,
      backendDiscovery: {
        ...defaultUSBConfig.backendDiscovery,
        enabled: false,
      },
      features: {
        ...defaultUSBConfig.features,
        enableDeveloperOptions: isDevelopment,
      },
      ui: {
        ...defaultUSBConfig.ui,
        showUSBIndicator: false,
      },
    };
  }

  // USB deployment configuration
  return {
    ...defaultUSBConfig,
    features: {
      ...defaultUSBConfig.features,
      enableDeveloperOptions: isDevelopment,
      enableAdminMode: import.meta.env.VITE_ENABLE_ADMIN_MODE !== "false",
    },
    performance: {
      ...defaultUSBConfig.performance,
      requestTimeout: parseInt(import.meta.env.VITE_API_TIMEOUT || "30000"),
    },
  };
};

// Export singleton instance
export const usbConfig = getUSBConfig();