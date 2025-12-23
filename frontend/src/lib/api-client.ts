import { BackendDiscoveryService } from './backend-discovery';

const STORAGE_KEY_BASE_URL = "sage_api_base_url";
const STORAGE_KEY_ADMIN_MODE = "sage_admin_mode";
const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";
// Increased timeout to 120 seconds (2 minutes) to accommodate slow CPU model inference
const REQUEST_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || "120000");
const IS_USB_DEPLOYMENT = import.meta.env.VITE_USB_DEPLOYMENT === "true";

interface RequestOptions {
  params?: Record<string, any>;
  timeout?: number;
}

export class ApiClient {
  private baseUrl: string;
  private initialized: boolean = false;
  private initPromise: Promise<void> | null = null;

  constructor() {
    this.baseUrl = this.loadBaseUrl();
    
    // Auto-initialize for USB deployment
    if (IS_USB_DEPLOYMENT) {
      this.initPromise = this.initializeForUSB();
    }
  }

  private loadBaseUrl(): string {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY_BASE_URL) || DEFAULT_BASE_URL;
    }
    return DEFAULT_BASE_URL;
  }

  /**
   * Initialize API client for USB deployment with backend discovery
   */
  private async initializeForUSB(): Promise<void> {
    if (this.initialized) return;

    try {
      console.log('🚀 Initializing API client for USB deployment...');
      const discoveredUrl = await BackendDiscoveryService.getCurrentBackendUrl();
      
      if (discoveredUrl !== this.baseUrl) {
        console.log(`🔄 Updating backend URL from ${this.baseUrl} to ${discoveredUrl}`);
        this.setBaseUrl(discoveredUrl);
      }
      
      this.initialized = true;
      console.log('✅ API client initialized successfully');
    } catch (error) {
      console.error('❌ Failed to initialize API client:', error);
      // Continue with default URL as fallback
      this.initialized = true;
    }
  }

  /**
   * Ensure the client is initialized before making requests
   */
  private async ensureInitialized(): Promise<void> {
    if (IS_USB_DEPLOYMENT && !this.initialized && this.initPromise) {
      await this.initPromise;
    }
  }

  public setBaseUrl(url: string): void {
    this.baseUrl = url;
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_BASE_URL, url);
    }
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  public static isAdminMode(): boolean {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY_ADMIN_MODE) === "true";
    }
    return false;
  }

  public static setAdminMode(enabled: boolean): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_ADMIN_MODE, enabled.toString());
    }
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      "X-User-ID": "local-user",
      "X-Username": "LocalUser",
      "X-User-Email": "local@example.com",
      "X-User-Role": ApiClient.isAdminMode() ? "admin" : "student",
      "X-School-ID": "local-school",
    };
    return headers;
  }

  private buildUrl(path: string, params?: Record<string, any>): string {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    return url.toString();
  }

  public async get<T = any>(
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    await this.ensureInitialized();
    
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      options.timeout || REQUEST_TIMEOUT
    );

    try {
      const url = this.buildUrl(path, options.params);
      const response = await fetch(url, {
        method: "GET",
        headers: this.getHeaders(),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      // Handle AbortError (timeout or manual abort)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(
          `Request timeout after ${(options.timeout || REQUEST_TIMEOUT) / 1000}s. ` +
          'The backend is processing your request. It may take longer than expected. ' +
          'Please check the backend status and try again.'
        );
      }
      
      // If request fails and we're in USB mode, try backend rediscovery
      if (IS_USB_DEPLOYMENT && error instanceof Error && error.name === 'TypeError') {
        console.log('🔄 Request failed, attempting backend rediscovery...');
        try {
          const newUrl = await BackendDiscoveryService.getCurrentBackendUrl();
          if (newUrl !== this.baseUrl) {
            this.setBaseUrl(newUrl);
            // Retry the request once with new URL
            const retryUrl = this.buildUrl(path, options.params);
            const retryResponse = await fetch(retryUrl, {
              method: "GET",
              headers: this.getHeaders(),
              signal: controller.signal,
            });
            
            if (retryResponse.ok) {
              return await retryResponse.json();
            }
          }
        } catch (rediscoveryError) {
          console.error('Backend rediscovery failed:', rediscoveryError);
        }
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  public async post<T = any>(
    path: string,
    body: any,
    options: RequestOptions = {}
  ): Promise<T> {
    await this.ensureInitialized();
    
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      options.timeout || REQUEST_TIMEOUT
    );

    try {
      const url = this.buildUrl(path, options.params);
      const response = await fetch(url, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      // Handle AbortError (timeout or manual abort)
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(
          `Request timeout after ${(options.timeout || REQUEST_TIMEOUT) / 1000}s. ` +
          'The backend is processing your request. It may take longer than expected. ' +
          'Please check the backend status and try again.'
        );
      }
      
      // If request fails and we're in USB mode, try backend rediscovery
      if (IS_USB_DEPLOYMENT && error instanceof Error && error.name === 'TypeError') {
        console.log('🔄 POST request failed, attempting backend rediscovery...');
        try {
          const newUrl = await BackendDiscoveryService.getCurrentBackendUrl();
          if (newUrl !== this.baseUrl) {
            this.setBaseUrl(newUrl);
            // Retry the request once with new URL
            const retryUrl = this.buildUrl(path, options.params);
            const retryResponse = await fetch(retryUrl, {
              method: "POST",
              headers: this.getHeaders(),
              body: JSON.stringify(body),
              signal: controller.signal,
            });
            
            if (retryResponse.ok) {
              return await retryResponse.json();
            }
          }
        } catch (rediscoveryError) {
          console.error('Backend rediscovery failed:', rediscoveryError);
        }
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export const apiClient = new ApiClient();
