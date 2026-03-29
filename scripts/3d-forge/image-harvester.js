#!/usr/bin/env node

/**
 * 3D Forge Image Harvester
 * Fetches high-quality reference images from Serper (Google Images) and Unsplash
 * for image-driven 3D modeling based on trend data.
 *
 * Usage:
 *   node image-harvester.js [--trend-file PATH] [--trend-id ID] [--limit N] [--dry-run]
 *
 * Env vars:
 *   SERPER_API_KEY      - Required for Google Images API
 *   UNSPLASH_ACCESS_KEY - Required for Unsplash API
 */

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");
const { URL } = require("url");

// Load .env
require('./lib/env').loadEnv();

// =============================================================================
// CLI ARGUMENTS & CONFIG
// =============================================================================

const args = process.argv.slice(2);
const config = {
  trendFile: null,
  trendId: null,
  limit: null,
  dryRun: false,
};

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === "--trend-file") {
    config.trendFile = args[++i];
  } else if (arg === "--trend-id") {
    config.trendId = args[++i];
  } else if (arg === "--limit") {
    config.limit = parseInt(args[++i], 10);
  } else if (arg === "--dry-run") {
    config.dryRun = true;
  }
}

const SERPER_API_KEY = process.env.SERPER_API_KEY;
const UNSPLASH_ACCESS_KEY = process.env.UNSPLASH_ACCESS_KEY;

const DEFAULT_TREND_FILE = "reports/trend-scan-latest.json";
const DATA_DIR = "data/3d-forge/refs";
// Higher targets = more reference pixels for vision compare + concept-generator (Serper/Unsplash quota permitting)
const TARGET_IMAGES_PER_TREND = 28;
const MIN_IMAGES_THRESHOLD = 12;

// =============================================================================
// LOGGING UTILITIES
// =============================================================================

function log(msg, level = "INFO") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${msg}`);
}

function logWarn(msg) {
  log(msg, "WARN");
}

function logError(msg) {
  log(msg, "ERROR");
}

function logDebug(msg) {
  if (process.env.DEBUG) {
    log(msg, "DEBUG");
  }
}

// =============================================================================
// TREND DATA LOADING
// =============================================================================

function loadTrendData() {
  const filePath = config.trendFile || DEFAULT_TREND_FILE;
  
  if (!fs.existsSync(filePath)) {
    if (config.dryRun) {
      logWarn(`Trend file not found (dry-run mode): ${filePath}`);
      return null; // Return null in dry-run to allow graceful handling
    }
    logError(`Trend file not found: ${filePath}`);
    process.exit(1);
  }

  try {
    const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
    
    if (!data.trends || !Array.isArray(data.trends)) {
      logError("Invalid trend file format: missing 'trends' array");
      process.exit(1);
    }

    let trends = data.trends;

    // Filter by --trend-id if specified
    if (config.trendId) {
      trends = trends.filter((t) => t.trend_id === config.trendId);
      if (trends.length === 0) {
        logError(`No trend found with ID: ${config.trendId}`);
        process.exit(1);
      }
    }

    // Apply limit if specified
    if (config.limit && config.limit > 0) {
      trends = trends.slice(0, config.limit);
    }

    log(`Loaded ${trends.length} trend(s) from ${filePath}`);
    return trends;
  } catch (err) {
    logError(`Failed to parse trend file: ${err.message}`);
    process.exit(1);
  }
}

// =============================================================================
// DIRECTORY MANAGEMENT
// =============================================================================

function ensureDirectory(dir) {
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (err) {
    logError(`Failed to create directory ${dir}: ${err.message}`);
    throw err;
  }
}

// =============================================================================
// HTTP UTILITIES
// =============================================================================

function fetchJson(urlString, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const protocol = url.protocol === "https:" ? https : http;

    const options = {
      method: "GET",
      headers: {
        "User-Agent": "3D-Forge-Image-Harvester/1.0",
        ...headers,
      },
      timeout: 10000,
    };

    const req = protocol.request(url, options, (res) => {
      let body = "";

      res.on("data", (chunk) => {
        body += chunk;
      });

      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(body));
          } catch (err) {
            reject(new Error(`Invalid JSON response: ${err.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${body.slice(0, 200)}`));
        }
      });
    });

    req.on("error", (err) => {
      reject(new Error(`Request failed: ${err.message}`));
    });

    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Request timeout"));
    });

    req.end();
  });
}

function postJson(urlString, payload, headers = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const protocol = url.protocol === "https:" ? https : http;
    const body = JSON.stringify(payload);

    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
        "User-Agent": "3D-Forge-Image-Harvester/1.0",
        ...headers,
      },
      timeout: 10000,
    };

    const req = protocol.request(url, options, (res) => {
      let responseBody = "";

      res.on("data", (chunk) => {
        responseBody += chunk;
      });

      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(responseBody));
          } catch (err) {
            reject(new Error(`Invalid JSON response: ${err.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${responseBody.slice(0, 200)}`));
        }
      });
    });

    req.on("error", (err) => {
      reject(new Error(`Request failed: ${err.message}`));
    });

    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Request timeout"));
    });

    req.write(body);
    req.end();
  });
}

function downloadFile(urlString, filePath) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const protocol = url.protocol === "https:" ? https : http;

    const options = {
      timeout: 15000,
      headers: {
        "User-Agent": "3D-Forge-Image-Harvester/1.0",
      },
    };

    const req = protocol.request(url, options, (res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        const file = fs.createWriteStream(filePath);

        res.pipe(file);

        file.on("finish", () => {
          file.close();
          resolve(filePath);
        });

        file.on("error", (err) => {
          fs.unlink(filePath, () => {});
          reject(err);
        });
      } else {
        reject(new Error(`HTTP ${res.statusCode}`));
      }
    });

    req.on("error", (err) => {
      reject(err);
    });

    req.on("timeout", () => {
      req.destroy();
      reject(new Error("Download timeout"));
    });

    req.end();
  });
}

// =============================================================================
// IMAGE SOURCE: SERPER (Google Images)
// =============================================================================

async function fetchFromSerper(keyword, queryCount = 24) {
  if (!SERPER_API_KEY) {
    logDebug("Serper API key not set, skipping Google Images");
    return [];
  }

  const images = [];
  const queries = [
    `${keyword} product photo high quality`,
    `${keyword} 3d print`,
    `${keyword} design reference`,
    `${keyword} white background`,
  ];

  for (const query of queries) {
    if (config.dryRun) {
      log(`[DRY-RUN] Would query Serper: "${query}"`);
      continue;
    }

    try {
      logDebug(`Querying Serper for: "${query}"`);

      const response = await postJson(
        "https://google.serper.dev/images",
        {
          q: query,
          num: queryCount,
        },
        {
          "X-API-KEY": SERPER_API_KEY,
        }
      );

      if (response.images && Array.isArray(response.images)) {
        for (const img of response.images) {
          // Extract width/height from imageMetadata if available
          const width = img.imageWidth || 0;
          const height = img.imageHeight || 0;

          // Prefer images >= 800px on at least one dimension
          if (Math.min(width, height) < 500) {
            logDebug(`Skipping image: too small (${width}x${height})`);
            continue;
          }

          images.push({
            source: "serper",
            source_url: img.imageUrl,
            page_url: img.link,
            width,
            height,
          });
        }
      }
    } catch (err) {
      logWarn(`Serper query failed for "${query}": ${err.message}`);
    }
  }

  return images;
}

// =============================================================================
// IMAGE SOURCE: UNSPLASH
// =============================================================================

async function fetchFromUnsplash(keyword, queryCount = 18) {
  if (!UNSPLASH_ACCESS_KEY) {
    logDebug("Unsplash API key not set, skipping Unsplash");
    return [];
  }

  const images = [];
  const queries = [keyword, `${keyword} lifestyle`, `${keyword} material`];

  for (const query of queries) {
    if (config.dryRun) {
      log(`[DRY-RUN] Would query Unsplash: "${query}"`);
      continue;
    }

    try {
      logDebug(`Querying Unsplash for: "${query}"`);

      const url = new URL("https://api.unsplash.com/search/photos");
      url.searchParams.append("query", query);
      url.searchParams.append("per_page", queryCount);

      const response = await fetchJson(url.toString(), {
        Authorization: `Client-ID ${UNSPLASH_ACCESS_KEY}`,
      });

      if (response.results && Array.isArray(response.results)) {
        for (const result of response.results) {
          images.push({
            source: "unsplash",
            source_url: result.urls.regular,
            page_url: result.links.html,
            width: result.width,
            height: result.height,
          });
        }
      }
    } catch (err) {
      logWarn(`Unsplash query failed for "${query}": ${err.message}`);
    }
  }

  return images;
}

// =============================================================================
// IMAGE DEDUPLICATION & QUALITY SCORING
// =============================================================================

function deduplicateImages(images) {
  const seen = new Set();
  const unique = [];

  for (const img of images) {
    if (!seen.has(img.source_url)) {
      seen.add(img.source_url);
      unique.push(img);
    }
  }

  return unique;
}

function scoreImageQuality(img) {
  let score = 50; // Base score

  // Resolution bonus (prefer larger images)
  const minDim = Math.min(img.width, img.height);
  if (minDim >= 1200) {
    score += 30;
  } else if (minDim >= 800) {
    score += 20;
  } else if (minDim >= 500) {
    score += 10;
  }

  // Aspect ratio bonus (prefer square or near-square for product photos)
  const aspectRatio = Math.max(img.width, img.height) / Math.min(img.width, img.height);
  if (aspectRatio < 1.3) {
    score += 10; // Square is good for product
  } else if (aspectRatio > 2.5) {
    score -= 10; // Panoramic is less useful
  }

  // Source preference
  if (img.source === "serper") {
    score += 5; // Google Images priority
  }

  return Math.min(100, Math.max(0, score));
}

function categorizeViewType(filename, index) {
  // Simple categorization based on order and filename hints
  const types = ["front_view", "side_view", "detail", "lifestyle", "material", "packaging"];
  
  if (filename.includes("detail")) return "detail";
  if (filename.includes("lifestyle")) return "lifestyle";
  if (filename.includes("material")) return "material";
  if (filename.includes("packaging")) return "packaging";
  if (filename.includes("side")) return "side_view";
  
  // Default cycling
  return types[index % types.length];
}

// =============================================================================
// IMAGE DOWNLOADING & PROCESSING
// =============================================================================

async function downloadImageWithRetry(imageData, filename, destDir, maxRetries = 1) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      logDebug(`Downloading: ${filename} (attempt ${attempt + 1})`);

      if (config.dryRun) {
        log(`[DRY-RUN] Would download: ${imageData.source_url} -> ${filename}`);
        return { success: true, filepath: path.join(destDir, filename) };
      }

      const filepath = path.join(destDir, filename);
      await downloadFile(imageData.source_url, filepath);

      // Verify file exists and has content
      const stats = fs.statSync(filepath);
      if (stats.size > 0) {
        return { success: true, filepath };
      } else {
        logWarn(`Downloaded file is empty: ${filename}`);
        fs.unlinkSync(filepath);
        if (attempt < maxRetries) continue;
        return { success: false, error: "Empty file" };
      }
    } catch (err) {
      logWarn(`Download failed (attempt ${attempt + 1}): ${err.message}`);
      if (attempt < maxRetries) {
        // Wait briefly before retry
        await new Promise((resolve) => setTimeout(resolve, 500));
        continue;
      }
      return { success: false, error: err.message };
    }
  }

  return { success: false, error: "Max retries exceeded" };
}

// =============================================================================
// MAIN HARVEST FUNCTION
// =============================================================================

async function harvestImagesForTrend(trend) {
  const trendId = trend.trend_id || trend.id;
  const keyword = trend.primary_keyword || trend.keyword || trend.name;

  log(`Harvesting images for trend: "${keyword}" (ID: ${trendId})`);

  // Ensure output directory
  const trendDir = path.join(DATA_DIR, trendId);
  const imagesDir = path.join(trendDir, "images");

  try {
    ensureDirectory(imagesDir);
  } catch (err) {
    logError(`Failed to create directories for trend ${trendId}`);
    return null;
  }

  // Fetch from all sources
  let allImages = [];

  if (config.dryRun) {
    // Generate mock image entries for dry-run so downstream stages have data
    log(`[DRY-RUN] Generating mock image references for "${keyword}"`);
    for (let m = 0; m < 5; m++) {
      allImages.push({
        source: m < 3 ? "mock_serper" : "mock_unsplash",
        source_url: `https://example.com/mock/${trendId}/img_${m + 1}.jpg`,
        page_url: `https://example.com/mock/${trendId}/page_${m + 1}`,
        width: 1024,
        height: 1024,
        title: `${keyword} reference ${m + 1}`,
      });
    }
    log(`  Generated ${allImages.length} mock image entries`);
  } else {
    log(`Fetching from Serper (Google Images)...`);
    const serperImages = await fetchFromSerper(keyword);
    allImages.push(...serperImages);
    log(`  Found ${serperImages.length} images from Serper`);

    log(`Fetching from Unsplash...`);
    const unsplashImages = await fetchFromUnsplash(keyword);
    allImages.push(...unsplashImages);
    log(`  Found ${unsplashImages.length} images from Unsplash`);
  }

  // Deduplicate
  allImages = deduplicateImages(allImages);
  log(`After deduplication: ${allImages.length} unique images`);

  // Check minimum threshold
  if (allImages.length < MIN_IMAGES_THRESHOLD) {
    logWarn(
      `Only ${allImages.length} images found for "${keyword}" (minimum: ${MIN_IMAGES_THRESHOLD}). Proceeding with caution.`
    );
  }

  // Score and sort
  allImages = allImages
    .map((img, idx) => ({
      ...img,
      quality_score: scoreImageQuality(img),
      view_type: categorizeViewType(img.source_url, idx),
    }))
    .sort((a, b) => b.quality_score - a.quality_score);

  // Select top images
  const selectedImages = allImages.slice(0, TARGET_IMAGES_PER_TREND);

  // Download selected images
  const manifest = {
    trend_id: trendId,
    keyword,
    image_count: 0,
    sources_used: [],
    images: [],
    harvested_at: new Date().toISOString(),
  };

  const sourcesSet = new Set();

  for (let i = 0; i < selectedImages.length; i++) {
    const img = selectedImages[i];
    sourcesSet.add(img.source);

    // Generate filename
    const ext = "jpg";
    const filename = `img_${String(i + 1).padStart(3, "0")}.${ext}`;

    // Download
    const downloadResult = await downloadImageWithRetry(img, filename, imagesDir);

    if (downloadResult.success) {
      const manifestEntry = {
        filename,
        source: img.source,
        source_url: img.source_url,
        page_url: img.page_url,
        width: img.width,
        height: img.height,
        view_type: img.view_type,
        quality_score: img.quality_score,
        downloaded: true,
      };

      manifest.images.push(manifestEntry);
      log(`  Downloaded: ${filename} (quality: ${img.quality_score}, view: ${img.view_type})`);
    } else {
      logWarn(`  Failed to download: ${filename}`);
      const manifestEntry = {
        filename,
        source: img.source,
        source_url: img.source_url,
        page_url: img.page_url,
        width: img.width,
        height: img.height,
        view_type: img.view_type,
        quality_score: img.quality_score,
        downloaded: false,
        download_error: downloadResult.error,
      };
      manifest.images.push(manifestEntry);
    }
  }

  manifest.sources_used = Array.from(sourcesSet);
  manifest.image_count = manifest.images.filter((img) => img.downloaded).length;

  // Write manifest
  const manifestPath = path.join(trendDir, "manifest.json");
  try {
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf8");
    log(`Manifest written: ${manifestPath}`);
  } catch (err) {
    logError(`Failed to write manifest: ${err.message}`);
    return null;
  }

  log(
    `Harvest complete for "${keyword}": ${manifest.image_count}/${selectedImages.length} images downloaded`
  );

  return manifest;
}

// =============================================================================
// MAIN ENTRY POINT
// =============================================================================

async function main() {
  log("========================================");
  log("3D Forge Image Harvester Started");
  log(`Mode: ${config.dryRun ? "DRY-RUN" : "NORMAL"}`);
  log(`Serper API: ${SERPER_API_KEY ? "configured" : "NOT SET"}`);
  log(`Unsplash API: ${UNSPLASH_ACCESS_KEY ? "configured" : "NOT SET"}`);
  log("========================================");

  if (!SERPER_API_KEY && !UNSPLASH_ACCESS_KEY) {
    logError(
      "No API keys configured. Set SERPER_API_KEY and/or UNSPLASH_ACCESS_KEY environment variables."
    );
    log("Proceeding with fallback (empty manifests)...");
  }

  // Load trends
  let trends = loadTrendData();
  
  // Handle dry-run with no trend file
  if (trends === null && config.dryRun) {
    log("DRY RUN: Skipping harvest (no trend data available)");
    log("Hint: Run trend-scanner in dry-run mode first to generate mock trends.");
    process.exit(0);
  }
  
  if (!trends || trends.length === 0) {
    logError("No trends loaded");
    process.exit(1);
  }

  // Process each trend
  const results = [];
  for (let i = 0; i < trends.length; i++) {
    const trend = trends[i];
    log(`\nProcessing trend ${i + 1}/${trends.length}...`);

    try {
      const manifest = await harvestImagesForTrend(trend);
      if (manifest) {
        results.push({
          trend_id: trend.trend_id || trend.id,
          keyword: trend.primary_keyword || trend.keyword || trend.name,
          success: true,
          image_count: manifest.image_count,
        });
      } else {
        results.push({
          trend_id: trend.trend_id || trend.id,
          keyword: trend.primary_keyword || trend.keyword || trend.name,
          success: false,
          error: "Manifest generation failed",
        });
      }
    } catch (err) {
      logError(`Unexpected error for trend ${trend.trend_id}: ${err.message}`);
      results.push({
        trend_id: trend.trend_id || trend.id,
        keyword: trend.keyword || trend.name,
        success: false,
        error: err.message,
      });
    }

    // Small delay between trends to avoid rate limits
    if (i < trends.length - 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  // Summary
  log("\n========================================");
  log("Harvest Summary");
  log("========================================");

  const successful = results.filter((r) => r.success).length;
  const failed = results.filter((r) => !r.success).length;
  const totalImages = results.reduce((sum, r) => sum + (r.image_count || 0), 0);

  for (const result of results) {
    const status = result.success ? "✓" : "✗";
    const count = result.success ? ` (${result.image_count} images)` : ` (${result.error})`;
    log(`${status} ${result.keyword}${count}`);
  }

  log(`\nTotal: ${successful} successful, ${failed} failed`);
  log(`Total images downloaded: ${totalImages}`);
  log(`Output directory: ${DATA_DIR}`);

  process.exit(failed > 0 ? 1 : 0);
}

// Run
main().catch((err) => {
  logError(`Fatal error: ${err.message}`);
  process.exit(1);
});
