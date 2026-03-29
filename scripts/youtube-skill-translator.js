const fs = require('fs');
const path = require('path');

/**
 * YouTube Skill Translator
 * Reads YouTube tutorial research and translates key techniques into MCP code patterns
 * Maps tutorials to applicable exercises and generates technique templates
 */

// Load YouTube research data
function loadYouTubeResearch() {
  const researchFile = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/data/youtube_research_2026-03-26.json';
  
  if (!fs.existsSync(researchFile)) {
    console.warn(`YouTube research file not found: ${researchFile}`);
    return { tutorials: [], generated_at: new Date().toISOString() };
  }

  try {
    return JSON.parse(fs.readFileSync(researchFile, 'utf8'));
  } catch (e) {
    console.error(`Failed to parse research file: ${e.message}`);
    return { tutorials: [], generated_at: new Date().toISOString() };
  }
}

// Map YouTube tutorials to skill exercises
function mapTutorialsToExercises(research) {
  const exerciseMap = {
    'lighting': ['EX_001_3POINT_LIGHTING', 'EX_003_NIGHT_LIGHTING'],
    'materials': ['EX_002_PBR_MATERIALS'],
    'environment': ['EX_004_HDRI_ENVIRONMENT'],
    'deformation': ['EX_005_IMPACT_DEFORMATION'],
    'camera': [],
    'rendering': [],
    'modeling': []
  };

  const mappedTutorials = [];

  if (!research.tutorials) {
    return mappedTutorials;
  }

  for (const tutorial of research.tutorials) {
    const techniques = tutorial.key_techniques || [];
    const applicableExercises = [];

    for (const technique of techniques) {
      const category = technique.category || 'general';
      const exercises = exerciseMap[category] || [];
      applicableExercises.push(...exercises);
    }

    mappedTutorials.push({
      title: tutorial.title,
      url: tutorial.url,
      duration_minutes: tutorial.duration_minutes,
      key_techniques: techniques,
      applicable_exercises: [...new Set(applicableExercises)],
      forensic_relevance: calculateForensicRelevance(tutorial),
      priority: assignPriority(tutorial)
    });
  }

  return mappedTutorials;
}

// Calculate forensic scene relevance
function calculateForensicRelevance(tutorial) {
  const forensicKeywords = [
    'lighting', 'materials', 'vehicle', 'impact', 'damage',
    'crash', 'collision', 'deformation', 'environment',
    'realistic', 'cinematic', 'environment'
  ];

  const title = (tutorial.title || '').toLowerCase();
  const description = (tutorial.description || '').toLowerCase();
  const fullText = `${title} ${description}`;

  const relevantKeywords = forensicKeywords.filter(kw => fullText.includes(kw));
  return {
    score: Math.min(relevantKeywords.length / forensicKeywords.length, 1.0),
    matching_keywords: relevantKeywords
  };
}

// Assign priority based on forensic relevance and difficulty
function assignPriority(tutorial) {
  const relevance = calculateForensicRelevance(tutorial);
  const relevanceScore = relevance.score;
  const durationBonus = tutorial.duration_minutes <= 20 ? 0.2 : 0;
  
  const priority = Math.min(relevanceScore + durationBonus, 1.0);
  
  if (priority >= 0.7) return 'high';
  if (priority >= 0.4) return 'medium';
  return 'low';
}

// Generate technique templates for the 4 forensic scenes
function generateTechniqueTemplates(mappedTutorials) {
  const scenes = [
    'parking_lot_incident',
    'highway_collision',
    'warehouse_impact',
    'precision_evidence_capture'
  ];

  const templates = {};

  for (const scene of scenes) {
    templates[scene] = {
      scene_name: scene,
      applicable_techniques: selectTechniquesForScene(scene, mappedTutorials),
      lighting_setup: generateLightingTemplate(scene),
      material_setup: generateMaterialTemplate(scene),
      environment_setup: generateEnvironmentTemplate(scene),
      deformation_setup: generateDeformationTemplate(scene)
    };
  }

  return templates;
}

// Select techniques relevant to specific scene
function selectTechniquesForScene(scene, tutorials) {
  const sceneRequirements = {
    parking_lot_incident: {
      keywords: ['night', 'sodium', 'vapor', 'parking', 'asphalt'],
      priority: ['night_lighting', 'pbr_materials']
    },
    highway_collision: {
      keywords: ['daylight', 'hdri', 'impact', 'deformation'],
      priority: ['3_point_lighting', 'impact_deformation', 'hdri_environment']
    },
    warehouse_impact: {
      keywords: ['indoor', 'tungsten', 'metal', 'concrete'],
      priority: ['pbr_materials', '3_point_lighting']
    },
    precision_evidence_capture: {
      keywords: ['detail', 'close-up', 'texture', 'material'],
      priority: ['pbr_materials', '3_point_lighting']
    }
  };

  const requirements = sceneRequirements[scene] || { keywords: [], priority: [] };
  const selected = [];

  for (const tutorial of tutorials) {
    const match = tutorial.applicable_exercises.length > 0;
    const isHighPriority = requirements.priority.some(p =>
      tutorial.applicable_exercises.join(' ').includes(p)
    );

    if (match || isHighPriority) {
      selected.push({
        title: tutorial.title,
        exercises: tutorial.applicable_exercises,
        priority: isHighPriority ? 'high' : 'medium'
      });
    }
  }

  return selected;
}

// Generate lighting template for scene
function generateLightingTemplate(scene) {
  const templates = {
    parking_lot_incident: {
      type: 'night_sodium_vapor',
      description: 'Dark parking lot with sodium vapor street lamps',
      world_strength: 0.5,
      world_color: [0.005, 0.005, 0.015],
      primary_lights: [
        { type: 'SPOT', energy: 800, color: [1.0, 0.65, 0.2], name: 'sodium_main' }
      ]
    },
    highway_collision: {
      type: 'daylight_3point',
      description: 'Bright daylight with realistic 3-point setup',
      world_strength: 1.2,
      world_color: [0.9, 0.95, 1.0],
      primary_lights: [
        { type: 'AREA', energy: 1000, color: [1.0, 1.0, 1.0], name: 'key' },
        { type: 'AREA', energy: 500, color: [1.0, 1.0, 1.0], name: 'fill' }
      ]
    },
    warehouse_impact: {
      type: 'industrial_tungsten',
      description: 'Warm tungsten warehouse lighting',
      world_strength: 0.8,
      world_color: [0.2, 0.18, 0.15],
      primary_lights: [
        { type: 'AREA', energy: 1200, color: [1.0, 0.85, 0.6], name: 'tungsten_main' }
      ]
    },
    precision_evidence_capture: {
      type: 'studio_keyed',
      description: 'Professional studio lighting for detail capture',
      world_strength: 0.3,
      world_color: [0.1, 0.1, 0.12],
      primary_lights: [
        { type: 'AREA', energy: 500, color: [1.0, 1.0, 1.0], name: 'key' },
        { type: 'AREA', energy: 200, color: [1.0, 1.0, 1.0], name: 'fill' }
      ]
    }
  };
  return templates[scene] || templates.highway_collision;
}

// Generate material template for scene
function generateMaterialTemplate(scene) {
  return {
    vehicles: {
      car_paint: { metallic: 0.9, roughness: 0.2 },
      glass: { transmission: 0.95, ior: 1.52 },
      tires: { roughness: 0.95, metallic: 0.0 }
    },
    environment: {
      asphalt: { roughness: 0.9, metallic: 0.0 },
      concrete: { roughness: 0.8, metallic: 0.0 },
      steel: { roughness: 0.3, metallic: 0.95 }
    },
    scene_specific: scene === 'parking_lot_incident' ? 'asphalt' : 'concrete'
  };
}

// Generate environment template for scene
function generateEnvironmentTemplate(scene) {
  const templates = {
    parking_lot_incident: {
      hdri_type: 'night_urban',
      sky_type: 'dark_starry',
      time_of_day: 'night',
      weather: 'clear'
    },
    highway_collision: {
      hdri_type: 'daylight_outdoor',
      sky_type: 'bright_blue',
      time_of_day: 'midday',
      weather: 'clear'
    },
    warehouse_impact: {
      hdri_type: 'indoor_warehouse',
      sky_type: 'industrial',
      time_of_day: 'day',
      weather: 'indoor'
    },
    precision_evidence_capture: {
      hdri_type: 'neutral_gray',
      sky_type: 'studio',
      time_of_day: 'studio',
      weather: 'controlled'
    }
  };
  return templates[scene] || { hdri_type: 'daylight', sky_type: 'blue' };
}

// Generate deformation template for scene
function generateDeformationTemplate(scene) {
  return {
    impact_zones: {
      front_end: { severity: 0.8, radius: 2.0 },
      side_panel: { severity: 0.6, radius: 1.5 },
      roof: { severity: 0.3, radius: 1.0 }
    },
    deformation_type: scene.includes('collision') ? 'frontal_impact' : 'general_damage'
  };
}

// Main execution
function translateAllTechniques() {
  console.log('[TRANSLATOR] Loading YouTube research...');
  const research = loadYouTubeResearch();

  console.log(`[TRANSLATOR] Found ${research.tutorials?.length || 0} tutorials`);
  const mappedTutorials = mapTutorialsToExercises(research);

  console.log('[TRANSLATOR] Generating technique templates for 4 forensic scenes...');
  const templates = generateTechniqueTemplates(mappedTutorials);

  const output = {
    generated_at: new Date().toISOString(),
    version: '1.0',
    tutorial_mappings: mappedTutorials,
    forensic_scene_templates: templates,
    summary: {
      total_tutorials_processed: research.tutorials?.length || 0,
      total_techniques_extracted: mappedTutorials.reduce((sum, t) => sum + t.key_techniques.length, 0),
      scenes_templated: Object.keys(templates).length
    }
  };

  const outputFile = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/data/translated_techniques.json';
  fs.writeFileSync(outputFile, JSON.stringify(output, null, 2));

  console.log(`[TRANSLATOR] Saved to ${outputFile}`);
  return output;
}

module.exports = {
  loadYouTubeResearch,
  mapTutorialsToExercises,
  calculateForensicRelevance,
  generateTechniqueTemplates,
  translateAllTechniques
};
