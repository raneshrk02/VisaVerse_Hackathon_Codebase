/**
 * Backend Discovery Service for USB Deployment
 * 
 * This service automatically discovers the backend URL when running in USB mode.
 * It tries multiple strategies to find the correct backend endpoint.
 */

interface BackendInfo {
  url: string;
  port: number;
  version: string;
  status: 'healthy' | 'unhealthy';
}

interface DiscoveryResult {
  success: boolean;
  backend?: BackendInfo;
  error?: string;
  attempts: Array<{
    url: string;
    success: boolean;
    error?: string;
    responseTime?: number;
  }>;
}

export class BackendDiscoveryService {
  private static readonly COMMON_PORTS = [8001];
  private static readonly DISCOVERY_TIMEOUT = 5000; // 5 seconds per attempt
  private static readonly MAX_CONCURRENT_ATTEMPTS = 3;
  
  private static readonly STORAGE_KEY = 'sage_discovered_backend';
  private static readonly CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  /**
   * Discover the backend URL automatically
   */
  public static async discoverBackend(): Promise<DiscoveryResult> {
    console.log('🔍 Starting backend discovery...');
    
    // First, try cached result if it's still valid
    const cached = this.getCachedBackend();
    if (cached) {
      console.log('📋 Using cached backend:', cached.url);
      const isHealthy = await this.checkBackendHealth(cached.url);
      if (isHealthy.success) {
        return {
          success: true,
          backend: cached,
          attempts: [{ url: cached.url, success: true, responseTime: isHealthy.responseTime }]
        };
      } else {
        console.log('⚠️ Cached backend is unhealthy, starting fresh discovery');
        this.clearCachedBackend();
      }
    }

    // Generate candidate URLs to test
    const candidates = this.generateCandidateUrls();
    console.log('🎯 Testing candidates:', candidates);

    const attempts: DiscoveryResult['attempts'] = [];
    
    // Test candidates in batches to avoid overwhelming the system
    for (let i = 0; i < candidates.length; i += this.MAX_CONCURRENT_ATTEMPTS) {
      const batch = candidates.slice(i, i + this.MAX_CONCURRENT_ATTEMPTS);
      
      const batchPromises = batch.map(async (url) => {
        const startTime = Date.now();
        try {
          const health = await this.checkBackendHealth(url);
          const responseTime = Date.now() - startTime;
          
          attempts.push({
            url,
            success: health.success,
            responseTime,
            error: health.error
          });

          if (health.success && health.backend) {
            return health.backend;
          }
        } catch (error) {
          attempts.push({
            url,
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error'
          });
        }
        return null;
      });

      const batchResults = await Promise.all(batchPromises);
      const successfulBackend = batchResults.find(result => result !== null);
      
      if (successfulBackend) {
        console.log('✅ Backend discovered:', successfulBackend.url);
        this.cacheBackend(successfulBackend);
        
        return {
          success: true,
          backend: successfulBackend,
          attempts
        };
      }
    }

    console.log('❌ Backend discovery failed');
    return {
      success: false,
      error: 'No healthy backend found on any tested port',
      attempts
    };
  }

  /**
   * Check if a specific backend URL is healthy
   */
  private static async checkBackendHealth(baseUrl: string): Promise<{
    success: boolean;
    backend?: BackendInfo;
    error?: string;
    responseTime?: number;
  }> {
    const startTime = Date.now();
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.DISCOVERY_TIMEOUT);

      const response = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      const responseTime = Date.now() - startTime;

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}: ${response.statusText}`,
          responseTime
        };
      }

      const healthData = await response.json();
      
      // Validate that this is actually our SAGE backend
      if (healthData.service !== 'SAGE RAG API' && !healthData.status) {
        return {
          success: false,
          error: 'Not a SAGE backend',
          responseTime
        };
      }

      const port = new URL(baseUrl).port || (baseUrl.startsWith('https') ? '443' : '80');
      
      return {
        success: true,
        responseTime,
        backend: {
          url: baseUrl,
          port: parseInt(port),
          version: healthData.version || '1.0.0',
          status: healthData.status === 'healthy' ? 'healthy' : 'unhealthy'
        }
      };

    } catch (error) {
      const responseTime = Date.now() - startTime;
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        responseTime
      };
    }
  }

  /**
   * Generate candidate URLs to test based on current location and common patterns
   */
  private static generateCandidateUrls(): string[] {
    const candidates: string[] = [];
    const currentHost = window.location.hostname;
    const protocols = window.location.protocol === 'https:' ? ['https', 'http'] : ['http'];

    // Strategy 1: Same host, different ports
    for (const protocol of protocols) {
      for (const port of this.COMMON_PORTS) {
        candidates.push(`${protocol}://${currentHost}:${port}`);
      }
    }

    // Strategy 2: Localhost variants (for development)
    if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
      for (const port of this.COMMON_PORTS) {
        candidates.push(`http://localhost:${port}`);
        candidates.push(`http://127.0.0.1:${port}`);
      }
    }

    // Strategy 3: Environment variable fallback
    const envApiUrl = import.meta.env.VITE_API_BASE_URL;
    if (envApiUrl && !candidates.includes(envApiUrl)) {
      candidates.unshift(envApiUrl); // Try env URL first
    }

    // Remove duplicates and return
    return [...new Set(candidates)];
  }

  /**
   * Cache the discovered backend for faster subsequent loads
   */
  private static cacheBackend(backend: BackendInfo): void {
    const cacheData = {
      backend,
      timestamp: Date.now()
    };
    
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(cacheData));
    } catch (error) {
      console.warn('Failed to cache backend info:', error);
    }
  }

  /**
   * Get cached backend if it's still valid
   */
  private static getCachedBackend(): BackendInfo | null {
    try {
      const cached = localStorage.getItem(this.STORAGE_KEY);
      if (!cached) return null;

      const cacheData = JSON.parse(cached);
      const age = Date.now() - cacheData.timestamp;
      
      if (age > this.CACHE_DURATION) {
        this.clearCachedBackend();
        return null;
      }

      return cacheData.backend;
    } catch (error) {
      console.warn('Failed to read cached backend info:', error);
      this.clearCachedBackend();
      return null;
    }
  }

  /**
   * Clear cached backend info
   */
  private static clearCachedBackend(): void {
    try {
      localStorage.removeItem(this.STORAGE_KEY);
    } catch (error) {
      console.warn('Failed to clear cached backend info:', error);
    }
  }

  /**
   * Get the current backend URL (from cache or discovery)
   */
  public static async getCurrentBackendUrl(): Promise<string> {
    const cached = this.getCachedBackend();
    if (cached) {
      return cached.url;
    }

    const discovery = await this.discoverBackend();
    if (discovery.success && discovery.backend) {
      return discovery.backend.url;
    }

    // Fallback to environment variable
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
  }
}