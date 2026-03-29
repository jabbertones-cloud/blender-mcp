#!/usr/bin/env node

/**
 * 3D Forge Concept Generator
 * Transforms reference images + trend data into Blender MCP instruction sets
 *
 * Usage: node concept-generator.js [--trend-id ID] [--concepts-per-trend N] [--platform TARGET] [--limit N] [--dry-run]
 *
 * Reads:
 *   - data/3d-forge/refs/{trend_id}/manifest.json (reference images)
 *   - reports/trend-scan-latest.json (trend metadata)
 *
 * Outputs:
 *   - data/3d-forge/concepts/{concept_id}.json (per concept)
 *   - reports/concept-generation-latest.json (summary)
 */

const fs = require("fs");
const path = require("path");
const http = require("http");
const { randomUUID } = require("crypto");

// Load .env
require('./lib/env').loadEnv();

// ============================================================================
// Configuration & Logging
// ============================================================================

const PLATFORM_CONSTRAINTS = {
  etsy_stl: {
    watertight: true,
    min_wall_mm: 1.5,
    format: "stl",
    max_tris: 100000,
  },
  roblox_ugc: {
    watertight: true,
    max_tris: 4000,
    format: "fbx",
    attachment: ["hat", "hair", "back"],
  },
  cults3d: {
    watertight: true,
    min_wall_mm: 1.5,
    format: "stl",
    max_tris: 100000,
  },
  game_asset: {
    watertight: false,
    max_tris: 50000,
    format: "glb",
    pbr: true,
  },
};

const DEFAULT_OPTIONS = {
  trendsDir: "reports",
  refsDir: "data/3d-forge/refs",
  conceptsDir: "data/3d-forge/concepts",
  conceptsPerTrend: 3,
  platform: "game_asset",
  dryRun: false,
  /** Max trends to process (forge-orchestrator passes --limit) */
  maxTrends: null,
};

let LOG_LEVEL = "info";
const log = {
  debug: (msg, data) => {
    if (LOG_LEVEL === "debug") {
      console.error(`[DEBUG] ${msg}`, data ? JSON.stringify(data, null, 2) : "");
    }
  },
  info: (msg, data) => {
    console.error(`[INFO] ${msg}`, data ? JSON.stringify(data, null, 2) : "");
  },
  warn: (msg, data) => {
    console.error(`[WARN] ${msg}`, data ? JSON.stringify(data, null, 2) : "");
  },
  error: (msg, data) => {
    console.error(`[ERROR] ${msg}`, data ? JSON.stringify(data, null, 2) : "");
  },
};

// ============================================================================
// Material Type Mapping
// ============================================================================

const KEYWORD_TO_MATERIAL_MAP = {
  // Plastic products
  "desk organizer": "plastic",
  "phone stand": "plastic",
  "cable organizer": "plastic",
  "container": "plastic",
  "storage box": "plastic",
  "drawer organizer": "plastic",
  "keyboard": "plastic",
  "mouse": "plastic",
  "charging dock": "plastic",
  "pen holder": "plastic",
  "phone case": "plastic",
  "screen protector": "plastic",
  "usb hub": "plastic",
  "speaker": "plastic",
  "headphone stand": "plastic",

  // Metal products
  "jewelry": "metal_gold",
  "ring": "metal_gold",
  "necklace": "metal_gold",
  "bracelet": "metal_gold",
  "watch": "metal_silver",
  "keychain": "metal_silver",
  "desk lamp": "metal_brushed",
  "bookend": "metal_brushed",
  "shelf bracket": "metal_brushed",
  "mirror frame": "metal_silver",
  "picture frame": "metal_gold",
  "coat rack": "metal_brushed",
  "door handle": "metal_chrome",
  "hardware": "metal_brushed",

  // Ceramic/Glass products
  "vase": "ceramic",
  "mug": "ceramic",
  "cup": "ceramic",
  "plate": "ceramic",
  "bowl": "ceramic",
  "planter": "ceramic",
  "pot": "ceramic",
  "tea set": "ceramic",
  "water glass": "glass",
  "wine glass": "glass",
  "jar": "glass",
  "bottle": "glass",

  // Wood products
  "coaster": "wood",
  "cutting board": "wood",
  "utensil holder": "wood",
  "wooden box": "wood",
  "frame": "wood",
  "shelf": "wood",
  "stand": "wood",
  "pen": "wood",

  // Fabric/Textile
  "pillow": "fabric",
  "cushion": "fabric",
  "pouch": "fabric",
  "bag": "fabric",
  "mat": "fabric",

  // Rubber/Silicone
  "phone grip": "rubber",
  "gasket": "rubber",
  "seal": "rubber",
  "bumper": "rubber",

  // Composite/Mixed
  "phone holder": "plastic_metal",
  "tablet stand": "plastic_metal",
  "monitor stand": "metal_plastic",
  "desk pad": "fabric_rubber",
};

function inferMaterialType(trendKeyword, description) {
  // Normalize inputs
  const keyword = (trendKeyword || "").toLowerCase().trim();
  const desc = (description || "").toLowerCase().trim();
  const combinedText = `${keyword} ${desc}`;

  // Direct keyword match with highest priority
  if (KEYWORD_TO_MATERIAL_MAP[keyword]) {
    return KEYWORD_TO_MATERIAL_MAP[keyword];
  }

  // Partial keyword matching (check each keyword)
  for (const [mappedKeyword, material] of Object.entries(KEYWORD_TO_MATERIAL_MAP)) {
    if (combinedText.includes(mappedKeyword)) {
      return material;
    }
  }

  // Heuristic-based inference from description
  if (combinedText.includes("metal")) return "metal_brushed";
  if (combinedText.includes("gold")) return "metal_gold";
  if (combinedText.includes("silver")) return "metal_silver";
  if (combinedText.includes("chrome")) return "metal_chrome";
  if (combinedText.includes("ceramic")) return "ceramic";
  if (combinedText.includes("glass")) return "glass";
  if (combinedText.includes("wood")) return "wood";
  if (combinedText.includes("plastic")) return "plastic";
  if (combinedText.includes("rubber")) return "rubber";
  if (combinedText.includes("silicone")) return "rubber";
  if (combinedText.includes("fabric")) return "fabric";
  if (combinedText.includes("textile")) return "fabric";
  if (combinedText.includes("leather")) return "leather";

  // Default fallback
  return "plastic";
}

function getMaterialKeywords(materialType) {
  const materialKeywordMap = {
    plastic: ["plastic", "acrylonitrile butadiene styrene", "abs", "pvc", "polycarbonate", "acrylic"],
    metal_gold: ["gold", "brass", "champagne", "rose gold", "metal", "shiny"],
    metal_silver: ["silver", "aluminum", "stainless steel", "chrome", "metallic", "brushed metal"],
    metal_brushed: ["brushed", "matte metal", "anodized", "powder coat"],
    metal_chrome: ["chrome", "chromium", "polished metal", "reflective"],
    ceramic: ["ceramic", "porcelain", "clay", "glazed"],
    glass: ["glass", "transparent", "translucent", "borosilicate"],
    wood: ["wood", "oak", "walnut", "bamboo", "maple", "birch", "natural fiber"],
    fabric: ["fabric", "cloth", "textile", "cotton", "polyester", "linen"],
    rubber: ["rubber", "silicone", "tpr", "thermoplastic", "elastomer"],
    leather: ["leather", "suede", "nubuck", "faux leather"],
    fabric_rubber: ["fabric", "rubber", "silicone", "hybrid"],
    plastic_metal: ["plastic", "metal", "composite"],
  };

  return materialKeywordMap[materialType] || ["material"];
}
// ============================================================================
// Argument Parsing
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { ...DEFAULT_OPTIONS };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--trend-id") {
      opts.trendId = args[++i];
    } else if (arg === "--concepts-per-trend") {
      opts.conceptsPerTrend = parseInt(args[++i], 10);
    } else if (arg === "--platform") {
      opts.platform = args[++i];
    } else if (arg === "--dry-run") {
      opts.dryRun = true;
    } else if (arg === "--debug") {
      LOG_LEVEL = "debug";
    } else if (arg === "--limit") {
      opts.maxTrends = parseInt(args[++i], 10);
    }
  }

  return opts;
}

// ============================================================================
// File I/O Utilities
// ============================================================================

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function readJSON(filePath, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (err) {
    log.debug(`Failed to read JSON: ${filePath}`, err.message);
    return fallback;
  }
}

function writeJSON(filePath, data) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
  log.info(`Wrote: ${filePath}`);
}

function readImageAsBase64(imagePath) {
  try {
    const buffer = fs.readFileSync(imagePath);
    return buffer.toString("base64");
  } catch (err) {
    log.error(`Failed to read image: ${imagePath}`, err.message);
    return null;
  }
}

// ============================================================================
// Trend & Reference Loading
// ============================================================================

function loadTrendData(trendsDir, trendId) {
  const trendFilePath = path.join(trendsDir, "trend-scan-latest.json");
  const trendData = readJSON(trendFilePath);

  if (!trendData || !trendData.trends) {
    log.error("Failed to load trend data", { path: trendFilePath });
    return null;
  }

  if (trendId) {
    const trend = trendData.trends.find((t) => t.trend_id === trendId);
    return trend ? [trend] : [];
  }

  return trendData.trends || [];
}


/**
 * Load trend scan results from trend-scanner.js output
 * Extracts keywords and product categories for concept generation
 * Returns enriched trend data object with scan metadata
 */
function loadTrendScanResults(trendsDir = "reports") {
  const trendScanPath = path.join(trendsDir, "trend-scan-latest.json");
  const trendScanData = readJSON(trendScanPath);

  if (!trendScanData || !trendScanData.trends) {
    log.debug("No trend scan results available", { path: trendScanPath });
    return { keywords: [], categories: [], loaded: false };
  }

  // Extract keywords and categories from scan results
  const allKeywords = [];
  const allCategories = [];
  
  for (const trend of trendScanData.trends) {
    if (trend.keywords && Array.isArray(trend.keywords)) {
      allKeywords.push(...trend.keywords);
    }
    if (trend.primary_keyword) {
      allKeywords.push(trend.primary_keyword);
    }
    if (trend.category) {
      allCategories.push(trend.category);
    }
  }

  // Remove duplicates
  const uniqueKeywords = [...new Set(allKeywords)];
  const uniqueCategories = [...new Set(allCategories)];

  log.info("Loaded trend scan results", {
    path: trendScanPath,
    trends_found: trendScanData.trends.length,
    keywords_extracted: uniqueKeywords.length,
    categories_extracted: uniqueCategories.length,
  });

  return {
    keywords: uniqueKeywords,
    categories: uniqueCategories,
    trend_demand_scores: trendScanData.trends.map(t => ({
      keyword: t.primary_keyword,
      score: t.demand_score,
      velocity: t.velocity,
    })),
    loaded: true,
    source_file: trendScanPath,
  };
}

function loadReferenceImages(refsDir, trendId) {
  const manifestPath = path.join(refsDir, trendId, "manifest.json");
  const manifest = readJSON(manifestPath);

  if (!manifest || !manifest.images) {
    log.warn(`No reference images found for trend: ${trendId}`);
    return [];
  }

  const trendDir = path.dirname(manifestPath);
  const imagesDir = path.join(trendDir, "images");
  const images = manifest.images.map((img) => {
    // Check images/ subdirectory first, then trend dir root
    const filePath = fs.existsSync(path.join(imagesDir, img.filename))
      ? path.join(imagesDir, img.filename)
      : path.join(trendDir, img.filename);

    // Check if image exists locally
    if (fs.existsSync(filePath)) {
      return {
        ...img,
        local_path: filePath,
        base64: null, // Will be encoded on demand
      };
    }

    // Otherwise use URL if available
    return img;
  });

  return images;
}

/**
 * Load quality refinements generated by quality-feedback-loop.js
 * Returns refinements object or empty object if file doesn't exist
 */
function loadQualityRefinements(configDir = "config/3d-forge") {
  const refinementsPath = path.join(configDir, "prompt-refinements.json");
  const refinements = readJSON(refinementsPath, {});
  
  if (Object.keys(refinements).length > 0) {
    log.info("Loaded quality refinements", { path: refinementsPath });
  }
  
  return refinements;
}

// ============================================================================
// Vision API Integration (Gemini primary, OpenAI fallback)
// ============================================================================

/**
 * Extract and parse JSON from LLM response text.
 * Handles markdown code blocks, truncated JSON, and other formatting issues.
 */
function extractJSON(text) {
  // Strip markdown code fences
  let jsonStr = text;
  const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    jsonStr = jsonMatch[1];
  }
  jsonStr = jsonStr.trim();

  // Try direct parse first
  try {
    return JSON.parse(jsonStr);
  } catch (e) {
    // Try to repair truncated JSON by closing open structures
    log.debug("JSON parse failed, attempting repair", { error: e.message });
  }

  // Find the last complete blender_step and truncate there
  const stepsMatch = jsonStr.match(/"blender_steps"\s*:\s*\[/);
  if (stepsMatch) {
    // Find last complete object in the steps array
    const lastCompleteStep = jsonStr.lastIndexOf('}');
    if (lastCompleteStep > 0) {
      let repaired = jsonStr.substring(0, lastCompleteStep + 1);
      // Count open braces/brackets to close them
      const opens = (repaired.match(/[{\[]/g) || []).length;
      const closes = (repaired.match(/[}\]]/g) || []).length;
      const diff = opens - closes;
      for (let i = 0; i < diff; i++) {
        // Heuristic: close arrays before objects
        if (repaired.lastIndexOf('[') > repaired.lastIndexOf('{')) {
          repaired += ']';
        } else {
          repaired += '}';
        }
      }
      try {
        return JSON.parse(repaired);
      } catch (e2) {
        log.debug("Repaired JSON still invalid", { error: e2.message });
      }
    }
  }

  throw new Error(`Could not parse JSON from response: ${jsonStr.substring(0, 100)}...`);
}

/**
 * Prepare base64-encoded images from the image list.
 * Returns array of { base64, mime_type } objects.
 */
function detectMimeFromBytes(buffer) {
  if (buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4E && buffer[3] === 0x47) return "image/png";
  if (buffer[0] === 0xFF && buffer[1] === 0xD8 && buffer[2] === 0xFF) return "image/jpeg";
  if (buffer[0] === 0x47 && buffer[1] === 0x49 && buffer[2] === 0x46) return "image/gif";
  if (buffer[0] === 0x52 && buffer[1] === 0x49 && buffer[2] === 0x46 && buffer[3] === 0x46) return "image/webp";
  return "image/jpeg"; // default fallback
}

function prepareImagePayloads(images, maxImages = 5) {
  const MAX_IMAGE_BYTES = 4 * 1024 * 1024; // 4MB to stay under Anthropic 5MB limit
  const payloads = [];
  // Sort images by file size ascending so we pick smaller ones first
  const sortedImages = [...images].sort((a, b) => {
    try {
      const sA = a.local_path && fs.existsSync(a.local_path) ? fs.statSync(a.local_path).size : Infinity;
      const sB = b.local_path && fs.existsSync(b.local_path) ? fs.statSync(b.local_path).size : Infinity;
      return sA - sB;
    } catch { return 0; }
  });
  for (const img of sortedImages.slice(0, maxImages)) {
    if (img.local_path && fs.existsSync(img.local_path)) {
      try {
        const buffer = fs.readFileSync(img.local_path);
        if (buffer.length > MAX_IMAGE_BYTES) {
          log.warn(`Skipping oversized image (${(buffer.length/1024/1024).toFixed(1)}MB): ${img.local_path}`);
          continue;
        }
        const mime = detectMimeFromBytes(buffer);
        const base64 = buffer.toString("base64");
        payloads.push({ base64, mime_type: mime });
      } catch (err) {
        log.warn(`Failed to read image: ${img.local_path}`, { error: err.message });
      }
    }
  }
  return payloads;
}

/**
 * Call Gemini Vision API (primary — free tier generous, working key)
 */
async function callGeminiVision(images, trendMetadata, platformConstraints, trendScanResults = {}) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY not set");
  const refinements = loadQualityRefinements();
  const imagePayloads = prepareImagePayloads(images);
  if (imagePayloads.length === 0) throw new Error("No valid images to process");

  const systemPrompt = buildSystemPrompt(refinements);
  const userPrompt = buildUserPrompt(trendMetadata, platformConstraints, refinements, trendScanResults);

  // Build Gemini parts array: text first, then images
  const parts = [
    { text: systemPrompt + "\\n\\n" + userPrompt },
    ...imagePayloads.map((img) => ({
      inline_data: { mime_type: img.mime_type, data: img.base64 },
    })),
  ];

  const requestBody = {
    contents: [{ parts }],
    generationConfig: {
      maxOutputTokens: 4096,
      temperature: 0.7,
      responseMimeType: "application/json",
    },
  };

  log.debug("Gemini API request", {
    model: "gemini-2.0-flash",
    image_count: imagePayloads.length,
  });

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Gemini API error: ${response.status} ${errText.substring(0, 300)}`);
  }

  const result = await response.json();

  // Extract content from Gemini response
  const content = result.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!content) throw new Error("No content in Gemini response");

  // Extract token usage
  const usageMeta = result.usageMetadata || {};
  const inputTokens = usageMeta.promptTokenCount || 0;
  const outputTokens = usageMeta.candidatesTokenCount || 0;
  // Gemini Flash is effectively free / very cheap
  const estimatedCost = (inputTokens * 0.0001 + outputTokens * 0.0004) / 1000;

  log.info("Gemini API response received", {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    estimated_cost_usd: estimatedCost.toFixed(6),
    provider: "gemini-2.0-flash",
  });

  const concept = extractJSON(content);

  return {
    concept,
    usage: {
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: inputTokens + outputTokens,
      estimated_cost_usd: estimatedCost,
      provider: "gemini-2.0-flash",
    },
  };
}

/**
 * Call OpenAI Vision API (fallback)
 */
async function callOpenAIVision(images, trendMetadata, platformConstraints, trendScanResults = {}) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY not set");
  const refinements = loadQualityRefinements();
  const imagePayloads = prepareImagePayloads(images);
  if (imagePayloads.length === 0) throw new Error("No valid images to process");

  const systemPrompt = buildSystemPrompt(refinements);
  const userPrompt = buildUserPrompt(trendMetadata, platformConstraints, refinements, trendScanResults);

  // OpenAI format: image_url with data URI
  const imageContent = imagePayloads.map((img) => ({
    type: "image_url",
    image_url: { url: `data:${img.mime_type};base64,${img.base64}`, detail: "low" },
  }));

  const requestBody = {
    model: "gpt-4o",
    max_tokens: 4096,
    messages: [
      { role: "system", content: systemPrompt },
      {
        role: "user",
        content: [{ type: "text", text: userPrompt }, ...imageContent],
      },
    ],
  };

  log.debug("OpenAI API request", {
    model: "gpt-4o",
    image_count: imageContent.length,
  });

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenAI API error: ${response.status} ${error.substring(0, 300)}`);
  }

  const result = await response.json();
  const usage = result.usage || {};
  const inputTokens = usage.prompt_tokens || 0;
  const outputTokens = usage.completion_tokens || 0;
  const estimatedCost = (inputTokens * 0.0025 + outputTokens * 0.01) / 1000;

  log.info("OpenAI API response received", {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    estimated_cost_usd: estimatedCost.toFixed(4),
    provider: "gpt-4o",
  });

  const content = result.choices?.[0]?.message?.content;
  if (!content) throw new Error("No content in OpenAI response");

  const concept = extractJSON(content);

  return {
    concept,
    usage: {
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: inputTokens + outputTokens,
      estimated_cost_usd: estimatedCost,
      provider: "gpt-4o",
    },
  };
}

/**
 * Call Anthropic Claude Vision API (second fallback)
 */
async function callAnthropicVision(images, trendMetadata, platformConstraints, trendScanResults = {}) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY not set");
  const refinements = loadQualityRefinements();
  const imagePayloads = prepareImagePayloads(images);
  if (imagePayloads.length === 0) throw new Error("No valid images to process");

  const systemPrompt = buildSystemPrompt(refinements);
  const userPrompt = buildUserPrompt(trendMetadata, platformConstraints, refinements, trendScanResults);

  // Anthropic format: source.type base64
  const imageContent = imagePayloads.map((img) => ({
    type: "image",
    source: { type: "base64", media_type: img.mime_type, data: img.base64 },
  }));

  const requestBody = {
    model: "claude-haiku-4-5-20251001",
    max_tokens: 8192,
    system: systemPrompt + "\\n\\nIMPORTANT: Output ONLY raw JSON. Do NOT wrap in markdown code blocks. No ```json``` fences.",
    messages: [
      {
        role: "user",
        content: [{ type: "text", text: userPrompt }, ...imageContent],
      },
    ],
  };

  log.debug("Anthropic API request", {
    model: "claude-haiku-4.5",
    image_count: imageContent.length,
  });

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(requestBody),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Anthropic API error: ${response.status} ${errText.substring(0, 300)}`);
  }

  const result = await response.json();
  const content = result.content?.[0]?.text;
  if (!content) throw new Error("No content in Anthropic response");

  const inputTokens = result.usage?.input_tokens || 0;
  const outputTokens = result.usage?.output_tokens || 0;
  // Sonnet pricing: $3/MTok in, $15/MTok out
  const estimatedCost = (inputTokens * 3 + outputTokens * 15) / 1000000;

  log.info("Anthropic API response received", {
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    estimated_cost_usd: estimatedCost.toFixed(4),
    provider: "claude-haiku-4.5",
  });

  const concept = extractJSON(content);

  return {
    concept,
    usage: {
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: inputTokens + outputTokens,
      estimated_cost_usd: estimatedCost,
      provider: "claude-haiku-4.5",
    },
  };
}

/**
 * Local Ollama llava — last resort when cloud vision is quota-blocked.
 */
async function callOllamaVision(images, trendMetadata, platformConstraints, trendScanResults = {}) {
  const refinements = loadQualityRefinements();
  const imagePayloads = prepareImagePayloads(images);
  if (imagePayloads.length === 0) throw new Error("No valid images to process");

  const systemPrompt = buildSystemPrompt(refinements);
  const userPrompt = buildUserPrompt(trendMetadata, platformConstraints, refinements, trendScanResults);
  const fullPrompt = `${systemPrompt}\n\n${userPrompt}\n\nOutput ONLY raw JSON for the concept. No markdown fences.`;

  const model = process.env.OLLAMA_VISION_MODEL || "llava:7b";
  const host = process.env.OLLAMA_HOST || "127.0.0.1";
  const port = parseInt(process.env.OLLAMA_PORT || "11434", 10);

  const requestBody = JSON.stringify({
    model,
    prompt: fullPrompt,
    images: imagePayloads.map((img) => img.base64),
    stream: false,
  });

  const text = await new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: host,
        port,
        path: "/api/generate",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(requestBody),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            if (res.statusCode !== 200) {
              reject(new Error(`Ollama ${res.statusCode}: ${data.slice(0, 300)}`));
              return;
            }
            const parsed = JSON.parse(data);
            resolve(parsed.response || "");
          } catch (e) {
            reject(e);
          }
        });
      }
    );
    req.on("error", reject);
    req.setTimeout(300000, () => {
      req.destroy();
      reject(new Error("Ollama request timeout"));
    });
    req.write(requestBody);
    req.end();
  });

  if (!text || !String(text).trim()) throw new Error("Empty Ollama response");

  const concept = extractJSON(text);
  log.info("Ollama vision response received", { provider: model, local: true });

  return {
    concept,
    usage: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      estimated_cost_usd: 0,
      provider: model,
    },
  };
}

/**
 * Multi-provider vision call: tries Gemini → Anthropic → OpenAI → Ollama (local).
 */
async function callVisionAPI(images, trendMetadata, platformConstraints, trendScanResults = {}) {
  const errors = [];

  // Try Gemini first (cheapest)
  if (process.env.GEMINI_API_KEY) {
    try {
      return await callGeminiVision(images, trendMetadata, platformConstraints, trendScanResults);
    } catch (err) {
      errors.push(`Gemini: ${err.message}`);
      log.warn("Gemini Vision failed", { error: err.message });
    }
  }

  // Try Anthropic second (good vision, working key)
  if (process.env.ANTHROPIC_API_KEY) {
    try {
      return await callAnthropicVision(images, trendMetadata, platformConstraints, trendScanResults);
    } catch (err) {
      errors.push(`Anthropic: ${err.message}`);
      log.warn("Anthropic Vision failed", { error: err.message });
    }
  }

  // Fallback to OpenAI
  if (process.env.OPENAI_API_KEY) {
    try {
      return await callOpenAIVision(images, trendMetadata, platformConstraints, trendScanResults);
    } catch (err) {
      errors.push(`OpenAI: ${err.message}`);
      log.warn("OpenAI Vision failed", { error: err.message });
    }
  }

  // Local Ollama (llava) — free, works when cloud keys are exhausted
  if (process.env.OLLAMA_SKIP_CONCEPT_VISION !== "1") {
    try {
      return await callOllamaVision(images, trendMetadata, platformConstraints, trendScanResults);
    } catch (err) {
      errors.push(`Ollama: ${err.message}`);
      log.warn("Ollama Vision failed", { error: err.message });
    }
  }

  throw new Error(`All vision providers failed:\\n${errors.join("\\n")}`);
}

function buildSystemPrompt(refinements = {}) {
  // Build base prompt with Blender 5.1 constraints
  let basePrompt = `You are an expert 3D modeling director who translates product reference photos into precise Blender 5.1 MCP instructions. You study reference images deeply — proportions, materials, construction geometry, surface details — and output step-by-step build instructions that a Blender automation system can execute.

CRITICAL PARAMETER TYPE RULES (violations will crash the pipeline):
- "size" parameter in create_object MUST be a SINGLE FLOAT NUMBER (e.g. 1.0, 2.5), NEVER an array [1,2,3]
  WRONG: "size": [2.0, 2.0, 2.0]
  RIGHT: "size": 2.0
  RIGHT: "size": 2.5, "scale": [1.0, 1.0, 1.0]
- For non-uniform dimensions, use SEPARATE "scale" parameter (array is OK there)
  scale: [0.5, 1.0, 2.0] ← scale IS a float array
- "location" must be [x, y, z] array of floats, e.g. [0.0, 5.0, -3.2]
- "rotation" must be [x, y, z] array of floats in radians, e.g. [0.0, 1.57, 0.0]
- Subdivision modifier type is "SUBSURF" not "SUBDIVISION_SURFACE"
- set_material "color" must be exactly [R, G, B, A] (4 floats, 0-1 range), never 3 or 7 values
  RIGHT: "color": [0.8, 0.2, 0.1, 1.0]
- boolean_operation: both "object" and "target" must exist. Create objects BEFORE referencing them
- execute_python code: use tuples for Vector math (1,2,3) not lists [1,2,3]. Lists don't support / operator
- Object names may get ".001" suffix if duplicated — use bpy.context.active_object when possible
- use_auto_smooth is removed in Blender 5.x — skip it
- ALL string values in Python code params must use SINGLE QUOTES only (not double quotes — double quotes break the pipeline)

DO NOT output this in params sections:
- Lists for size parameter: "size": [1, 2, 3] ← WRONG
- Division of lists: dimensions / 2 will crash if dimensions is a list
- Mismatched color array lengths: always 4 values [R, G, B, A]
`;

  // Inject quality refinements if available
  if (refinements.blocked_patterns && Object.keys(refinements.blocked_patterns).length > 0) {
    basePrompt += `\\n\\nPREVIOUSLY PROBLEMATIC PATTERNS TO AVOID:\\n`;
    for (const [pattern, reason] of Object.entries(refinements.blocked_patterns)) {
      basePrompt += `- ${pattern}: ${reason}\\n`;
    }
  }

  if (refinements.enhanced_constraints) {
    basePrompt += `\\n\\nENHANCED CONSTRAINTS FOR QUALITY:\\n`;
    if (refinements.enhanced_constraints.geometry_requirements) {
      basePrompt += `Geometry: ${refinements.enhanced_constraints.geometry_requirements}\\n`;
    }
    if (refinements.enhanced_constraints.material_requirements) {
      basePrompt += `Materials: ${refinements.enhanced_constraints.material_requirements}\\n`;
    }
    if (refinements.enhanced_constraints.export_requirements) {
      basePrompt += `Export: ${refinements.enhanced_constraints.export_requirements}\\n`;
    }
  }

  // Inject constraints from analysis.by_fix_category if available
  if (refinements.analysis && refinements.analysis.by_fix_category) {
    const categories = refinements.analysis.by_fix_category;
    
    // Extract high-frequency fixes by category
    for (const [category, issues] of Object.entries(categories)) {
      if (Array.isArray(issues) && issues.length > 0) {
        // Get top 2 issues by frequency for this category
        const topIssues = issues
          .sort((a, b) => parseFloat(b.frequency || 0) - parseFloat(a.frequency || 0))
          .slice(0, 2);
        
        if (topIssues.length > 0) {
          basePrompt += `\\n\\nCONSTRAINT [${category.toUpperCase()}]:\\n`;
          for (const issue of topIssues) {
            basePrompt += `- ${issue.issue}: ${issue.fix}\\n`;
          }
        }
      }
    }
  }

  // Add core guidance
  basePrompt += `\\n\\nFor each image, study:
- Overall silhouette and proportions (measure relative ratios)
- Geometric primitives that compose the shape (sphere, cylinder, cube, torus, etc.)
- Surface treatment (smooth, faceted, textured, organic, hard-surface)
- Material properties (matte/glossy/metallic/transparent, roughness, colors as hex)
- Functional features (hollow interior, holes, slots, hinges, joints)
- Approximate real-world dimensions in mm

Generate a COMPLETE Blender MCP build sequence. Each step must use one of these tool calls:
- blender_create_object(type, size, location, rotation) — size is a SINGLE FLOAT (e.g. 2.0, not [2,2,2])
- blender_modify_object(object_name, location/rotation/scale)
- blender_execute_python(code) — for edit mode ops, sculpting, complex geometry. Use SINGLE QUOTES in code
- blender_boolean_operation(object, target, operation: UNION/DIFFERENCE/INTERSECT)
- blender_apply_modifier(object_name, modifier_type, params) — use SUBSURF not SUBDIVISION_SURFACE
- blender_set_material(object_name, color, metallic, roughness, specular) — color is [R,G,B,A] 4 floats
- blender_shader_nodes(object_name, nodes) — for complex materials
- blender_uv_operations(object_name, action: smart_project)
- blender_cleanup(action: shade_smooth/remove_doubles/recalculate_normals)
- blender_export_file(filepath, format)

Output ONLY valid JSON, no markdown. Return exactly this structure:
{
  "name": "descriptive product name",
  "description": "what this is and why it sells",
  "visual_analysis": {
    "silhouette": "description",
    "proportions": { "key_measurement": "value_mm" },
    "materials": ["material description"],
    "colors": ["#hex"],
    "key_features": ["feature"]
  },
  "blender_steps": [
    {
      "step": 1,
      "tool": "blender_create_object",
      "params": { "type": "cylinder", "size": 0.5, "location": [0, 0, 0] },
      "description": "Create base cylinder for stem"
    }
  ],
  "estimated_dimensions_mm": [120, 120, 180],
  "estimated_tri_count": 5000,
  "difficulty": "low|medium|high"
}`;

  return basePrompt;
}

function buildUserPrompt(trendMetadata, platformConstraints, refinements = {}, trendScanResults = {}) {
  const category = trendMetadata.category || "unknown";
  const keyword = trendMetadata.primary_keyword || trendMetadata.keyword || "product";
  const constraintStr = JSON.stringify(platformConstraints, null, 2);

  let trendKeywordContext = "";
  if (trendScanResults.keywords && trendScanResults.keywords.length > 0) {
    const relevantKeywords = trendScanResults.keywords
      .filter(
        (kw) =>
          keyword.toLowerCase().includes(kw.toLowerCase()) ||
          kw.toLowerCase().includes(keyword.toLowerCase())
      )
      .slice(0, 5);
    if (relevantKeywords.length > 0) {
      trendKeywordContext = `\nRelated trending keywords from market scan: ${relevantKeywords.join(", ")}`;
    }
  }

  let userPromptText = `Analyze these reference images of a "${category}" product matching the keyword "${keyword}".

Platform Constraints:
${constraintStr}${trendKeywordContext}

Generate a complete, buildable Blender MCP instruction sequence for this product. Focus on:
1. Accurate proportions derived from the reference images
2. Geometric construction that minimizes triangle count while maintaining detail
3. Material assignments with realistic colors and properties
4. Features that make this product unique and sellable
5. Export format appropriate for the target platform

CRITICAL: Parameter type validation:
- Every "size" parameter MUST be a single float, not an array
- Never output "size": [x, y, z] — output "size": max_value instead
- Use "scale": [x_ratio, y_ratio, z_ratio] for non-uniform dimensions
- All numeric values must be numbers, not strings`;

  // Inject material specifications from refinements if available
  if (refinements.material_specifications) {
    userPromptText += `\n\nMATERIAL SPECIFICATIONS:\n${refinements.material_specifications}`;
  }

  // Inject lighting setup guidance if available
  if (refinements.lighting_improvements) {
    userPromptText += `\n\nLIGHTING SETUP:\n${refinements.lighting_improvements}`;
  }

  // Inject geometry validation requirements if available
  if (refinements.geometry_validation) {
    userPromptText += `\n\nGEOMETRY VALIDATION REQUIREMENTS:\n${refinements.geometry_validation}`;
  }

  userPromptText += `\n\nCRITICAL REMINDERS for parameter values:
- size must be a SINGLE NUMBER (float), never an array
- Use scale parameter for non-uniform dimensions (scale CAN be an array)
- All strings in code params use single quotes: 'text' not "text"
- location defaults to [0, 0, 0] if not specified
- Do NOT divide lists by scalars in Python — convert lists to scalars first

Return the JSON concept structure with all required fields.`;

  return userPromptText;
}

// ============================================================================
// Concept Generation & Variation
// ============================================================================

function generateConceptVariations(concept, count = 3) {
  const variations = [];

  // Original concept
  variations.push({
    variation_id: 0,
    name: concept.name,
    param_overrides: {},
    description: "Original design from reference images",
  });

  // Proportional variations (size +10%, -10%)
  if (count > 1) {
    variations.push({
      variation_id: 1,
      name: `${concept.name} — Large`,
      param_overrides: {
        scale: 1.1,
        dimension_adjustment: "10% larger proportions",
      },
      description: "Scaled up 10% for larger market segment",
    });
  }

  if (count > 2) {
    variations.push({
      variation_id: 2,
      name: `${concept.name} — Compact`,
      param_overrides: {
        scale: 0.9,
        dimension_adjustment: "10% smaller proportions",
      },
      description: "Scaled down 10% for compact variant",
    });
  }

  return variations;
}

async function generateConcept(
  trendMetadata,
  images,
  platformConstraints,
  dryRun = false,
  trendScanResults = {}
) {
  if (dryRun) {
    log.info("DRY RUN: Would call OpenAI Vision API", {
      trend_id: trendMetadata.trend_id,
      image_count: images.length,
    });
    return mockConcept(trendMetadata);
  }

  try {
    const { concept, usage } = await callVisionAPI(
      images,
      trendMetadata,
      platformConstraints,
      trendScanResults
    );

    // Add metadata
    concept.concept_id = randomUUID();
    concept.trend_id = trendMetadata.trend_id;
    concept.platform = platformConstraints.format;

    // Infer material type from trend keyword and description for skill matching
    const materialType = inferMaterialType(
      trendMetadata.primary_keyword || trendMetadata.keyword,
      concept.description
    );
    concept.material_type = materialType;
    concept.material_keywords = getMaterialKeywords(materialType);

    log.info("Added material information to concept", {
      concept_id: concept.concept_id,
      material_type: materialType,
    });
    concept.generated_at = new Date().toISOString();
    concept.api_usage = usage;
    concept.variations = generateConceptVariations(concept);

    return concept;
  } catch (err) {
    log.error("Failed to generate concept", {
      trend_id: trendMetadata.trend_id,
      error: err.message,
    });
    throw err;
  }
}

function mockConcept(trendMetadata) {
  // Mock concept for dry-run testing
  return {
    concept_id: randomUUID(),
    trend_id: trendMetadata.trend_id,
    name: `${trendMetadata.primary_keyword || trendMetadata.keyword} Concept`,
    description: `Mock 3D model for ${trendMetadata.category || 'general'}`,
    platform: "game_asset",
    generated_at: new Date().toISOString(),
    visual_analysis: {
      silhouette: "Mock analysis",
      proportions: { width: 100, height: 100, depth: 100 },
      materials: ["plastic", "metal"],
      colors: ["#FF0000", "#00FF00"],
      key_features: ["modular", "lightweight"],
    },
    blender_steps: [
      {
        step: 1,
        tool: "blender_create_object",
        params: { type: "cube", size: 1.0, location: [0, 0, 0] },
        description: "Create base cube",
      },
    ],
    estimated_dimensions_mm: [100, 100, 100],
    estimated_tri_count: 1000,
    difficulty: "low",
    variations: generateConceptVariations({
      name: `${trendMetadata.primary_keyword || trendMetadata.keyword} Concept`,
    }),
    material_type: inferMaterialType(
      trendMetadata.primary_keyword || trendMetadata.keyword,
      trendMetadata.category || 'general'
    ),
    material_keywords: getMaterialKeywords(
      inferMaterialType(
        trendMetadata.primary_keyword || trendMetadata.keyword,
        trendMetadata.category || 'general'
      )
    ),
    api_usage: {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      estimated_cost_usd: 0,
    },
  };
}

// ============================================================================
// Main Execution
// ============================================================================

async function main() {
  const opts = parseArgs();

  log.info("3D Forge Concept Generator started", {
    trend_id: opts.trendId || "all",
    concepts_per_trend: opts.conceptsPerTrend,
    platform: opts.platform,
    dry_run: opts.dryRun,
    max_trends: opts.maxTrends || null,
  });

  // Validate platform
  if (!PLATFORM_CONSTRAINTS[opts.platform]) {
    log.error("Invalid platform", {
      platform: opts.platform,
      available: Object.keys(PLATFORM_CONSTRAINTS),
    });
    process.exit(1);
  }

  // Load trends
  let trends = loadTrendData(opts.trendsDir, opts.trendId);
  if (!trends || trends.length === 0) {
    log.error("No trends loaded");
    process.exit(1);
  }

  if (opts.maxTrends && opts.maxTrends > 0 && trends.length > opts.maxTrends) {
    trends = trends.slice(0, opts.maxTrends);
    log.info("Limited trends per --limit", { processing: trends.length });
  }

  log.info("Trends loaded", { count: trends.length });

  // FIX 2: Load trend scan results to augment concept generation
  const trendScanResults = loadTrendScanResults(opts.trendsDir);
  if (trendScanResults.loaded) {
    log.info("Trend scan data integrated", {
      keywords_available: trendScanResults.keywords.length,
      categories_available: trendScanResults.categories.length,
    });
  }

  // Ensure output directory
  ensureDir(opts.conceptsDir);

  // Generation state
  const generatedConcepts = [];
  let totalTokens = 0;
  let totalCost = 0;

  // Process each trend
  for (const trend of trends) {
    log.info(`Processing trend: ${trend.trend_id}`);

    // Load reference images
    const images = loadReferenceImages(opts.refsDir, trend.trend_id);
    if (images.length === 0 && !opts.dryRun) {
      log.warn(`No reference images for trend: ${trend.trend_id}`);
      continue;
    }

    // Generate N concepts per trend
    for (let i = 0; i < opts.conceptsPerTrend; i++) {
      try {
        const platformConstraints = PLATFORM_CONSTRAINTS[opts.platform];
        const concept = await generateConcept(
          trend,
          images,
          platformConstraints,
          opts.dryRun,
          trendScanResults
        );

        // Save concept
        const conceptPath = path.join(opts.conceptsDir, `${concept.concept_id}.json`);
        writeJSON(conceptPath, concept);

        generatedConcepts.push({
          concept_id: concept.concept_id,
          trend_id: concept.trend_id,
          name: concept.name,
          difficulty: concept.difficulty,
          estimated_tri_count: concept.estimated_tri_count,
          api_cost_usd: concept.api_usage?.estimated_cost_usd || 0,
        });

        totalTokens += concept.api_usage?.total_tokens || 0;
        totalCost += concept.api_usage?.estimated_cost_usd || 0;

        log.info(`Generated concept: ${concept.concept_id}`, {
          name: concept.name,
          difficulty: concept.difficulty,
          variations: concept.variations.length,
        });

        // Rate limiting: wait 2s between API calls
        if (i < opts.conceptsPerTrend - 1 && !opts.dryRun) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      } catch (err) {
        log.error(`Failed to generate concept for trend ${trend.trend_id}`, {
          attempt: i + 1,
          error: err.message,
        });
      }
    }
  }

  // Write summary report
  const summary = {
    generated_at: new Date().toISOString(),
    total_concepts: generatedConcepts.length,
    platform: opts.platform,
    concepts: generatedConcepts,
    api_usage: {
      total_tokens: totalTokens,
      estimated_cost_usd: totalCost.toFixed(4),
    },
    trends_processed: trends.length,
  };

  const reportPath = path.join(opts.trendsDir, "concept-generation-latest.json");
  writeJSON(reportPath, summary);

  log.info("Concept generation complete", {
    total_generated: generatedConcepts.length,
    total_api_cost_usd: totalCost.toFixed(4),
    report: reportPath,
  });

  console.log(JSON.stringify(summary, null, 2));
}

main().catch((err) => {
  log.error("Fatal error", err.message);
  process.exit(1);
});
