#!/usr/bin/env node

/**
 * 3D Forge Trend Scanner
 *
 * Detects trending products/pop culture that can be turned into:
 * - 3D printable STL files
 * - Roblox UGC items
 * - Game assets
 *
 * Sources:
 * 1. Google Trends (via SERPER_API_KEY)
 * 2. Reddit (JSON API)
 * 3. Etsy trending (placeholder, requires ETSY_API_KEY)
 * 4. Roblox catalog API
 *
 * Usage:
 *   node trend-scanner.js [--dry-run] [--limit N] [--category CATEGORY]
 */

const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");
const { exec } = require("child_process");
const { promisify } = require("util");

const https = require("https");
const http = require("http");

// Load .env
require('./lib/env').loadEnv();

// ============================================================================
// Config & CLI Parsing
// ============================================================================

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const limitIdx = args.findIndex((a) => a === "--limit" || a.startsWith("--limit="));
const limit = limitIdx !== -1
  ? parseInt(args[limitIdx].includes("=") ? args[limitIdx].split("=")[1] : args[limitIdx + 1], 10) || 35
  : 35;
const categoryIdx = args.findIndex((a) => a === "--category" || a.startsWith("--category="));
const filterCategory = categoryIdx !== -1
  ? (args[categoryIdx].includes("=") ? args[categoryIdx].split("=")[1] : args[categoryIdx + 1]) || null
  : null;

const {
  SERPER_API_KEY = "",
  ETSY_API_KEY = "",
  REDDIT_USER_AGENT = "3DForge/1.0",
} = process.env;

const REPORTS_DIR = path.join(__dirname, "..", "..", "reports");
const DATA_DIR = path.join(__dirname, "..", "..", "data");

// Ensure directories exist
fs.mkdirSync(REPORTS_DIR, { recursive: true });
fs.mkdirSync(DATA_DIR, { recursive: true });

// ============================================================================
// Logging & Utilities
// ============================================================================

const log = {
  info: (msg, data = null) => {
    console.log(
      `[${new Date().toISOString()}] INFO: ${msg}`,
      data ? JSON.stringify(data, null, 2) : ""
    );
  },
  warn: (msg, data = null) => {
    console.warn(
      `[${new Date().toISOString()}] WARN: ${msg}`,
      data ? JSON.stringify(data, null, 2) : ""
    );
  },
  error: (msg, data = null) => {
    console.error(
      `[${new Date().toISOString()}] ERROR: ${msg}`,
      data ? JSON.stringify(data, null, 2) : ""
    );
  },
  debug: (msg, data = null) => {
    if (process.env.DEBUG) {
      console.log(
        `[${new Date().toISOString()}] DEBUG: ${msg}`,
        data ? JSON.stringify(data, null, 2) : ""
      );
    }
  },
};

// HTTP fetch helper
const httpFetch = (url, options = {}) => {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https") ? https : http;
    const req = client.get(url, options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${data.substring(0, 200)}`));
        } else {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve(data);
          }
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error("Request timeout"));
    });
  });
};

const httpPost = (url, body, headers = {}) => {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const client = urlObj.protocol === "https:" ? https : http;
    const jsonBody = JSON.stringify(body);
    const options = {
      method: "POST",
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(jsonBody),
        ...headers,
      },
    };
    const req = client.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${data.substring(0, 200)}`));
        } else {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve(data);
          }
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error("Request timeout"));
    });
    req.write(jsonBody);
    req.end();
  });
};

// Fuzzy keyword matching for deduplication
const levenshteinDistance = (a, b) => {
  const matrix = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  return matrix[b.length][a.length];
};

const fuzzyMatch = (str1, str2, threshold = 0.7) => {
  const dist = levenshteinDistance(str1.toLowerCase(), str2.toLowerCase());
  const maxLen = Math.max(str1.length, str2.length);
  const similarity = 1 - dist / maxLen;
  return similarity >= threshold;
};

// ============================================================================
// Category Detection
// ============================================================================

const CATEGORY_KEYWORDS = {
  desk_organizer: [
    "organizer",
    "holder",
    "desk",
    "storage",
    "container",
    "box",
    "caddy",
    "tray",
  ],
  phone_stand: [
    "phone stand",
    "phone holder",
    "mobile stand",
    "dock",
    "stand",
    "phone",
    "mounting",
  ],
  smart_home_mount: [
    "mount",
    "bracket",
    "wall mount",
    "holder mount",
    "alexa",
    "echo",
    "google home",
    "smart speaker",
  ],
  cosplay_prop: [
    "cosplay",
    "prop",
    "costume",
    "anime",
    "character",
    "sword",
    "weapon",
    "mask",
    "helmet",
    "armor",
  ],
  figurine: [
    "figurine",
    "statue",
    "miniature",
    "figure",
    "model",
    "toy",
    "collectible",
    "anime figure",
  ],
  planter: [
    "planter",
    "pot",
    "flower",
    "plant",
    "succulent",
    "garden",
    "vase",
  ],
  miniature: [
    "miniature",
    "mini",
    "diorama",
    "tiny",
    "small scale",
    "dungeon",
    "tabletop",
    "wargaming",
  ],
  roblox_hat: ["roblox hat", "hat", "headwear", "crown", "cap", "beanie"],
  roblox_wings: ["roblox wings", "wings", "fairy", "angel", "dragon"],
  roblox_hair: [
    "roblox hair",
    "hair",
    "roblox accessory",
    "head accessory",
  ],
  game_environment: [
    "environment",
    "building",
    "terrain",
    "rock",
    "tree",
    "landscape",
    "level",
    "map",
  ],
  game_prop: [
    "game asset",
    "game prop",
    "weapon",
    "tool",
    "furniture",
    "decoration",
    "asset",
  ],
};

const detectCategory = (keywords) => {
  const keywordStr = (keywords || []).join(" ").toLowerCase();
  const scores = {};

  for (const [category, catKeywords] of Object.entries(CATEGORY_KEYWORDS)) {
    scores[category] = catKeywords.filter((k) =>
      keywordStr.includes(k.toLowerCase())
    ).length;
  }

  const best = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  return best && best[1] > 0 ? best[0] : "miniature";
};

// ============================================================================
// Platform Fit Detection
// ============================================================================

const detectPlatformFit = (category, keywords = []) => {
  const keywordStr = (keywords || []).join(" ").toLowerCase();

  return {
    etsy_stl:
      category !== "roblox_hat" &&
      category !== "roblox_wings" &&
      category !== "roblox_hair",
    roblox_ugc:
      category.startsWith("roblox_") ||
      keywordStr.includes("roblox") ||
      category === "figurine" ||
      category === "cosplay_prop",
    cults3d:
      category !== "roblox_hat" &&
      category !== "roblox_wings" &&
      category !== "roblox_hair",
    game_asset:
      category === "game_environment" ||
      category === "game_prop" ||
      category === "figurine" ||
      keywordStr.includes("game") ||
      keywordStr.includes("asset"),
  };
};

// ============================================================================
// Trend Sources
// ============================================================================

/**
 * Google product trends via SERPER search API
 * Searches for trending 3D-printable and sellable product categories
 */
const scanGoogleTrends = async () => {
  if (dryRun) {
    log.info("DRY RUN: Would scan Google Trends (SERPER_API_KEY)");
    return [];
  }

  if (!SERPER_API_KEY) {
    log.warn("SERPER_API_KEY not configured, skipping Google Trends");
    return [];
  }

  const allTrends = [];

  // Product-focused search queries that reveal what people want to buy/make
  const searchQueries = [
    "trending 3d printed products 2026",
    "best selling STL files Etsy",
    "popular 3d print desk organizer",
    "trending Roblox UGC accessories",
    "popular cosplay props to 3d print",
    "best selling 3d printed phone stand",
    "trending anime figurines 3d print",
    "popular planters 3d printed",
    "game asset marketplace trending",
    "articulated 3d print popular",
  ];

  for (const query of searchQueries) {
    try {
      log.info(`Serper search: "${query}"...`);

      const res = await httpPost(
        "https://google.serper.dev/search",
        { q: query, num: 10, gl: "US", hl: "en" },
        { "X-API-KEY": SERPER_API_KEY }
      );

      // Extract product keywords from organic results + related searches
      const relatedSearches = (res.relatedSearches || []).map((r) => {
        const kw = (r.query || "").toLowerCase().trim();
        return {
          keywords: kw.split(/\s+/).filter((w) => w.length > 2),
          primary_keyword: kw,
          source: "google_trends",
          engagement_signal: 0.7, // Related searches = high intent
          velocity: "rising",
        };
      });

      allTrends.push(...relatedSearches);

      // Also extract product names from organic titles
      const organicTrends = (res.organic || []).slice(0, 5).map((r) => {
        const title = (r.title || "").toLowerCase();
        // Extract just the product part (before | or - or by)
        const cleanTitle = title.split(/[|\-–—]/)[0].trim().substring(0, 60);
        const words = cleanTitle.split(/\s+/).filter((w) => w.length > 2);
        return {
          keywords: words.slice(0, 6),
          primary_keyword: cleanTitle,
          source: "google_trends",
          engagement_signal: 0.5,
          velocity: "stable",
        };
      });

      allTrends.push(...organicTrends);

      // Rate limit: 200ms between queries
      await new Promise((resolve) => setTimeout(resolve, 200));
    } catch (err) {
      log.error(`Serper search failed for "${query}"`, { error: err.message });
    }
  }

  log.info(`Found ${allTrends.length} product trends from Google/Serper`);
  return allTrends;
};

/**
 * Reddit trending posts
 */
const scanReddit = async () => {
  if (dryRun) {
    log.info("DRY RUN: Would scan Reddit (r/3Dprinting, r/roblox, r/gaming, etc.)");
    return [];
  }

  const subreddits = [
    "3Dprinting",
    "roblox",
    "gaming",
    "cosplay",
    "functionalprint",
    "EtsySellers",
    "anime",
  ];
  const allTrends = [];

  for (const sub of subreddits) {
    try {
      log.info(`Scanning r/${sub}...`);

      const url = `https://www.reddit.com/r/${sub}/hot.json?limit=25`;
      const res = await httpFetch(url, {
        headers: {
          "User-Agent": REDDIT_USER_AGENT,
        },
      });

      const posts = (res.data?.children || [])
        .filter((c) => c.data && c.data.score > 50)
        .map((c) => {
          const post = c.data;
          const title = (post.title || "").toLowerCase();

          // Extract the product/object noun phrase, not the full post title
          // Remove common reddit prefixes and filler words
          let cleaned = title
            .replace(/^(i |my |just |finally |first |check out |look at |made a |printed a |designed a |modelled a |created a |built a |here'?s? )/gi, "")
            .replace(/\s*[\[\(].*?[\]\)]\s*/g, " ")  // remove [tags] and (notes)
            .replace(/[!?.,:;]+$/g, "")  // strip trailing punctuation
            .trim();

          // Take the first meaningful phrase (before conjunctions or long explanations)
          cleaned = cleaned.split(/\s+(for|with|from|using|after|because|but|and|that|which|how|what)\s+/i)[0] || cleaned;
          cleaned = cleaned.substring(0, 50).trim();

          // Skip posts that are clearly not about a product/object
          const skipPatterns = /^(does anyone|has anyone|can someone|question|psa|news|update|opinion|why do|what do|who else|am i the only|just wanted|anyone else)/i;
          if (skipPatterns.test(cleaned) || cleaned.length < 5) return null;

          const keywords = cleaned
            .split(/\s+/)
            .filter((w) => w.length > 2 && !/^(the|and|for|with|this|that|from|have|been|some|very|just|also|more|most|than|into|over|only|each|like|about)$/.test(w))
            .slice(0, 6);

          if (keywords.length < 2) return null;

          return {
            keywords,
            primary_keyword: cleaned,
            source: "reddit",
            subreddit: sub,
            engagement_signal: (post.score + (post.num_comments || 0)) / 1000,
            upvotes: post.score,
            comments: post.num_comments || 0,
          };
        })
        .filter(Boolean);

      allTrends.push(...posts);
      log.info(`Found ${posts.length} posts from r/${sub}`);
    } catch (err) {
      log.error(`Reddit r/${sub} scan failed`, { error: err.message });
    }
  }

  return allTrends;
};

/**
 * Roblox catalog trending items
 */
const scanRobloxCatalog = async () => {
  if (dryRun) {
    log.info("DRY RUN: Would scan Roblox catalog (bestselling accessories)");
    return [];
  }

  const categories = ["Accessories", "Clothing", "Bundles"];
  const allTrends = [];

  for (const cat of categories) {
    try {
      log.info(`Scanning Roblox catalog: ${cat}...`);

      const url = `https://catalog.roblox.com/v1/search/items?category=${cat}&sortType=2&limit=30`;
      const res = await httpFetch(url);

      const items = (res.data || []).map((item) => ({
        keywords: [item.name],
        primary_keyword: item.name,
        source: "roblox_catalog",
        category_roblox: cat,
        engagement_signal: (item.favoriteCount || 0) / 1000,
        favorites: item.favoriteCount || 0,
        sales_estimate: (item.favoriteCount || 0) * 0.5, // Rough estimate
      }));

      allTrends.push(...items);
      log.info(`Found ${items.length} items from Roblox ${cat}`);
    } catch (err) {
      log.error(`Roblox catalog ${cat} scan failed`, { error: err.message });
    }
  }

  return allTrends;
};

/**
 * Etsy trending (placeholder — requires ETSY_API_KEY)
 */
const scanEtsyTrending = async () => {
  if (dryRun) {
    log.info("DRY RUN: Would scan Etsy trending (ETSY_API_KEY)");
    return [];
  }

  if (!ETSY_API_KEY) {
    log.warn("ETSY_API_KEY not configured, skipping Etsy trending");
    return [];
  }

  try {
    log.info("Scanning Etsy trending...");
    // Placeholder: Etsy API integration would go here
    // For now, return empty since Etsy API requires OAuth2
    log.warn("Etsy API integration not yet implemented");
    return [];
  } catch (err) {
    log.error("Etsy trending scan failed", { error: err.message });
    return [];
  }
};

// ============================================================================
// Trend Deduplication & Scoring
// ============================================================================

const deduplicateTrends = (rawTrends) => {
  const merged = {};

  for (const trend of rawTrends) {
    const primaryKeyword = (trend.primary_keyword || "").toLowerCase().trim();
    if (!primaryKeyword) continue;

    // Try fuzzy match
    let found = false;
    for (const existingKey of Object.keys(merged)) {
      if (fuzzyMatch(primaryKeyword, existingKey, 0.75)) {
        // Merge
        merged[existingKey].sources.push(trend.source);
        merged[existingKey].keywords = [
          ...new Set([
            ...merged[existingKey].keywords,
            ...(trend.keywords || []),
          ]),
        ];
        merged[existingKey].source_data.push(trend);
        found = true;
        break;
      }
    }

    if (!found) {
      merged[primaryKeyword] = {
        keywords: [...new Set(trend.keywords || [primaryKeyword])],
        primary_keyword: trend.primary_keyword,
        sources: [trend.source],
        source_data: [trend],
      };
    }
  }

  return Object.values(merged);
};

const scoreTrends = (dedupTrends) => {
  return dedupTrends.map((trend) => {
    // Calculate normalized signals (0-100 scale each)
    const googleSignals = trend.source_data.filter((d) => d.source === "google_trends");
    const redditSignals = trend.source_data.filter((d) => d.source === "reddit");
    const robloxSignals = trend.source_data.filter((d) => d.source === "roblox_catalog");

    // Google: engagement_signal is already 0-1, boost for multi-source
    const googleSignal = googleSignals.length > 0
      ? Math.max(...googleSignals.map((d) => d.engagement_signal || 0))
      : 0;
    const googleScore = Math.min(100, googleSignal * 100 + (googleSignals.length > 1 ? 15 : 0));

    // Reddit: (score + comments) / 1000, so a 2000-upvote post = 2.0
    // Normalize: multiply by 30 to make a 1000-upvote post (~1.0) score ~30
    const redditSignal = redditSignals.reduce((sum, d) => sum + (d.engagement_signal || 0), 0);
    const redditScore = Math.min(100, redditSignal * 30 + (redditSignals.length > 1 ? 10 : 0));

    // Roblox: favoriteCount / 1000, so 50K favorites = 50.0
    // Already well-scaled, just cap at 100
    const robloxSignal = robloxSignals.length > 0
      ? Math.max(...robloxSignals.map((d) => d.engagement_signal || 0))
      : 0;
    const robloxScore = Math.min(100, robloxSignal * 2);

    // Category feasibility (some categories are easier to produce)
    const category = detectCategory(trend.keywords);
    const feasibilityScore = {
      desk_organizer: 90,
      phone_stand: 85,
      smart_home_mount: 80,
      planter: 88,
      figurine: 75,
      cosplay_prop: 70,
      miniature: 80,
      roblox_hat: 85,
      roblox_wings: 80,
      roblox_hair: 75,
      game_environment: 60,
      game_prop: 70,
    }[category] || 70;

    // Weighted demand score — Google has highest product intent, then Roblox (actual marketplace)
    const demand_score =
      googleScore * 0.35 +
      redditScore * 0.15 +
      robloxScore * 0.30 +
      feasibilityScore * 0.20;

    // Velocity (rising if Google shows rising trend)
    const velocity = trend.source_data.some(
      (d) => d.source === "google_trends" && d.velocity === "rising"
    )
      ? "rising"
      : "stable";

    return {
      trend_id: randomUUID(),
      keywords: trend.keywords.slice(0, 5),
      primary_keyword: trend.primary_keyword,
      category,
      sources: trend.sources,
      demand_score: Math.round(demand_score),
      velocity,
      platform_fit: detectPlatformFit(category, trend.keywords),
      suggested_products: generateSuggestedProducts(trend.primary_keyword),
      source_data: trend.source_data,
      timestamp: new Date().toISOString(),
    };
  });
};

const generateSuggestedProducts = (keyword) => {
  const variations = [
    `${keyword} - basic`,
    `${keyword} - premium`,
    `${keyword} - colorful`,
    `${keyword} set`,
  ];
  return variations.slice(0, 3);
};

// ============================================================================
// Main Scan & Output
// ============================================================================

const generateMockTrends = () => {
  // Generate realistic mock trends with correct schema for downstream use
  const mockTrendsData = [
    {
      trend_id: randomUUID(),
      keywords: ["mushroom", "lamp", "ambient", "decor"],
      primary_keyword: "mushroom lamp",
      category: "desk_organizer",
      sources: ["mock_google_trends", "mock_reddit"],
      demand_score: 78,
      velocity: "rising",
      platform_fit: {
        etsy_stl: true,
        roblox_ugc: false,
        cults3d: true,
        game_asset: true,
      },
      suggested_products: [
        "mushroom lamp - basic",
        "mushroom lamp - premium",
        "mushroom lamp set",
      ],
      source_data: [
        {
          source: "mock_google_trends",
          primary_keyword: "mushroom lamp",
          engagement_signal: 0.65,
          velocity: "rising",
        },
        {
          source: "mock_reddit",
          primary_keyword: "mushroom lamp",
          engagement_signal: 0.58,
          subreddit: "3Dprinting",
        },
      ],
      timestamp: new Date().toISOString(),
    },
    {
      trend_id: randomUUID(),
      keywords: ["anime", "hair", "roblox", "accessory"],
      primary_keyword: "anime hair roblox",
      category: "roblox_hair",
      sources: ["mock_roblox_catalog"],
      demand_score: 85,
      velocity: "rising",
      platform_fit: {
        etsy_stl: false,
        roblox_ugc: true,
        cults3d: false,
        game_asset: false,
      },
      suggested_products: [
        "anime hair roblox - basic",
        "anime hair roblox - premium",
        "anime hair roblox set",
      ],
      source_data: [
        {
          source: "mock_roblox_catalog",
          primary_keyword: "anime hair roblox",
          engagement_signal: 0.85,
          favorites: 12500,
        },
      ],
      timestamp: new Date().toISOString(),
    },
    {
      trend_id: randomUUID(),
      keywords: ["organizer", "minimalist", "desk", "storage"],
      primary_keyword: "minimalist desk organizer",
      category: "desk_organizer",
      sources: ["mock_google_trends", "mock_reddit"],
      demand_score: 72,
      velocity: "stable",
      platform_fit: {
        etsy_stl: true,
        roblox_ugc: false,
        cults3d: true,
        game_asset: false,
      },
      suggested_products: [
        "minimalist desk organizer - basic",
        "minimalist desk organizer - premium",
        "minimalist desk organizer set",
      ],
      source_data: [
        {
          source: "mock_google_trends",
          primary_keyword: "minimalist desk organizer",
          engagement_signal: 0.52,
        },
        {
          source: "mock_reddit",
          primary_keyword: "minimalist desk organizer",
          engagement_signal: 0.48,
          subreddit: "EtsySellers",
        },
      ],
      timestamp: new Date().toISOString(),
    },
    {
      trend_id: randomUUID(),
      keywords: ["dragon", "articulated", "figurine", "collectible"],
      primary_keyword: "dragon figurine articulated",
      category: "figurine",
      sources: ["mock_reddit"],
      demand_score: 68,
      velocity: "stable",
      platform_fit: {
        etsy_stl: true,
        roblox_ugc: true,
        cults3d: true,
        game_asset: true,
      },
      suggested_products: [
        "dragon figurine articulated - basic",
        "dragon figurine articulated - premium",
        "dragon figurine articulated set",
      ],
      source_data: [
        {
          source: "mock_reddit",
          primary_keyword: "dragon figurine articulated",
          engagement_signal: 0.68,
          subreddit: "3Dprinting",
          upvotes: 850,
          comments: 120,
        },
      ],
      timestamp: new Date().toISOString(),
    },
    {
      trend_id: randomUUID(),
      keywords: ["cyberpunk", "helmet", "cosplay", "prop"],
      primary_keyword: "cyberpunk helmet cosplay",
      category: "cosplay_prop",
      sources: ["mock_google_trends", "mock_reddit"],
      demand_score: 71,
      velocity: "rising",
      platform_fit: {
        etsy_stl: true,
        roblox_ugc: false,
        cults3d: true,
        game_asset: true,
      },
      suggested_products: [
        "cyberpunk helmet cosplay - basic",
        "cyberpunk helmet cosplay - premium",
        "cyberpunk helmet cosplay set",
      ],
      source_data: [
        {
          source: "mock_google_trends",
          primary_keyword: "cyberpunk helmet cosplay",
          engagement_signal: 0.61,
          velocity: "rising",
        },
        {
          source: "mock_reddit",
          primary_keyword: "cyberpunk helmet cosplay",
          engagement_signal: 0.55,
          subreddit: "cosplay",
        },
      ],
      timestamp: new Date().toISOString(),
    },
  ];

  return mockTrendsData;
};

const main = async () => {
  log.info("3D Forge Trend Scanner starting...", { dryRun, limit, filterCategory });

  if (dryRun) {
    log.info("DRY RUN MODE - Generating mock trend data");
    
    try {
      // Generate mock trends
      const mockTrends = generateMockTrends().slice(0, limit);
      
      // Write mock report
      const output = {
        generated_at: new Date().toISOString(),
        total_raw_trends: mockTrends.length,
        total_deduplicated: mockTrends.length,
        total_scored: mockTrends.length,
        category_filter: filterCategory,
        limit,
        trends: filterCategory
          ? mockTrends.filter((t) => t.category === filterCategory)
          : mockTrends,
      };

      const reportPath = path.join(REPORTS_DIR, "trend-scan-latest.json");
      fs.mkdirSync(REPORTS_DIR, { recursive: true });
      fs.writeFileSync(reportPath, JSON.stringify(output, null, 2));
      log.info("Mock report written", { path: reportPath });

      // Print summary table
      console.log("\n" + "=".repeat(100));
      console.log("DRY RUN: MOCK TRENDS BY DEMAND SCORE");
      console.log("=".repeat(100));
      console.table(
        output.trends.map((t) => ({
          keyword: t.primary_keyword,
          category: t.category,
          demand: t.demand_score,
          velocity: t.velocity,
          sources: t.sources.join(", "),
          etsy: t.platform_fit.etsy_stl ? "✓" : "",
          roblox: t.platform_fit.roblox_ugc ? "✓" : "",
          game: t.platform_fit.game_asset ? "✓" : "",
        }))
      );
      console.log("=".repeat(100) + "\n");

      log.info("Dry-run trend scan complete");
      process.exit(0);
    } catch (err) {
      log.error("Fatal error during dry-run", { error: err.message });
      process.exit(1);
    }
  }

  try {
    // Scan all sources in parallel
    const [googleTrends, redditTrends, robloxTrends, etsyTrends] =
      await Promise.all([
        scanGoogleTrends(),
        scanReddit(),
        scanRobloxCatalog(),
        scanEtsyTrending(),
      ]);

    const rawTrends = [
      ...googleTrends,
      ...redditTrends,
      ...robloxTrends,
      ...etsyTrends,
    ];

    log.info("Raw trends collected", { total: rawTrends.length });

    // Deduplicate
    const dedupTrends = deduplicateTrends(rawTrends);
    log.info("After deduplication", { total: dedupTrends.length });

    // Score
    const scoredTrends = scoreTrends(dedupTrends);

    // Filter by category if specified
    const filtered = filterCategory
      ? scoredTrends.filter((t) => t.category === filterCategory)
      : scoredTrends;

    // Sort by demand score and take top N
    const topTrends = filtered
      .sort((a, b) => b.demand_score - a.demand_score)
      .slice(0, limit);

    log.info("Top trends identified", {
      total: topTrends.length,
      category_filter: filterCategory,
    });

    // Write to file
    const output = {
      generated_at: new Date().toISOString(),
      total_raw_trends: rawTrends.length,
      total_deduplicated: dedupTrends.length,
      total_scored: scoredTrends.length,
      category_filter: filterCategory,
      limit,
      trends: topTrends,
    };

    const reportPath = path.join(REPORTS_DIR, "trend-scan-latest.json");
    fs.writeFileSync(reportPath, JSON.stringify(output, null, 2));
    log.info("Report written", { path: reportPath });

    // Print summary table
    console.log("\n" + "=".repeat(100));
    console.log("TOP TRENDS BY DEMAND SCORE");
    console.log("=".repeat(100));
    console.table(
      topTrends.map((t) => ({
        keyword: t.primary_keyword,
        category: t.category,
        demand: t.demand_score,
        velocity: t.velocity,
        sources: t.sources.join(", "),
        etsy: t.platform_fit.etsy_stl ? "✓" : "",
        roblox: t.platform_fit.roblox_ugc ? "✓" : "",
        game: t.platform_fit.game_asset ? "✓" : "",
      }))
    );
    console.log("=".repeat(100) + "\n");

    log.info("Trend scan complete");
    process.exit(0);
  } catch (err) {
    log.error("Fatal error during trend scan", { error: err.message });
    process.exit(1);
  }
};

main();
