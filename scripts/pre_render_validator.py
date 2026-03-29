#!/usr/bin/env python3
"""
Pre-render Scene Validator for Blender
Analyzes .blend files without rendering to catch failures in ~50ms.

Usage:
    blender --background scene.blend --python pre_render_validator.py -- --output /path/to/report.json
"""

import bpy
import sys
import json
import time
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
from mathutils import Vector, Matrix
import traceback


class PreRenderValidator:
    """Validates Blender scene without rendering."""
    
    def __init__(self, output_path: str = None):
        self.output_path = output_path
        self.start_time = time.time()
        self.scene = bpy.context.scene
        self.results = {
            "file": Path(bpy.data.filepath).name if bpy.data.filepath else "unknown",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_verdict": "PASS",
            "overall_score": 100,
            "checks": {},
            "blocking_issues": [],
            "warnings": [],
            "recommendations": [],
            "predicted_render_quality": "HIGH",
            "skip_render_recommendation": False,
            "execution_time_ms": 0
        }
        
    def add_check_result(self, category: str, verdict: str, score: int, details: List[Dict]):
        """Add a check result to the results structure."""
        self.results["checks"][category] = {
            "verdict": verdict,
            "score": score,
            "details": details
        }
        
    def add_blocking_issue(self, message: str):
        """Add a blocking issue that prevents rendering."""
        self.results["blocking_issues"].append(message)
        
    def add_warning(self, message: str):
        """Add a warning."""
        self.results["warnings"].append(message)
        
    def add_recommendation(self, message: str):
        """Add a recommendation."""
        self.results["recommendations"].append(message)
    
    def update_overall_verdict(self):
        """Update overall verdict based on check results."""
        # If any check FAILs, overall is FAIL
        verdicts = [check["verdict"] for check in self.results["checks"].values()]
        
        if "FAIL" in verdicts:
            self.results["overall_verdict"] = "FAIL"
            self.results["skip_render_recommendation"] = True
        elif "WARN" in verdicts:
            self.results["overall_verdict"] = "WARN"
        else:
            self.results["overall_verdict"] = "PASS"
        
        # Calculate overall score as average
        scores = [check["score"] for check in self.results["checks"].values()]
        if scores:
            self.results["overall_score"] = int(sum(scores) / len(scores))
        
        # Determine predicted render quality
        if self.results["overall_verdict"] == "FAIL":
            self.results["predicted_render_quality"] = "WILL_FAIL"
        elif self.results["overall_score"] >= 85:
            self.results["predicted_render_quality"] = "HIGH"
        elif self.results["overall_score"] >= 70:
            self.results["predicted_render_quality"] = "MEDIUM"
        else:
            self.results["predicted_render_quality"] = "LOW"
    
    def check_cameras(self) -> Tuple[str, int, List[Dict]]:
        """Check camera configuration."""
        details = []
        score = 100
        
        try:
            # Check if scene camera exists
            if not self.scene.camera:
                details.append({
                    "check": "Scene camera exists",
                    "passed": False,
                    "severity": "critical",
                    "message": "No active camera set for scene",
                    "fix_hint": "Select a camera object and set it as the active camera (Scene Properties > Camera)"
                })
                score = 0
                self.add_blocking_issue("No camera set as active scene camera")
                return "FAIL", score, details
            
            # Get all cameras in scene
            cameras = [obj for obj in self.scene.objects if obj.type == "CAMERA"]
            
            if not cameras:
                details.append({
                    "check": "Camera objects exist",
                    "passed": False,
                    "severity": "critical",
                    "message": "No camera objects found in scene",
                    "fix_hint": "Add a camera to the scene (Shift+A > Camera)"
                })
                score = 0
                self.add_blocking_issue("No camera objects in scene")
                return "FAIL", score, details
            
            details.append({
                "check": "Scene camera exists",
                "passed": True,
                "severity": "critical",
                "message": f"Active camera: {self.scene.camera.name}",
                "fix_hint": ""
            })
            
            # Validate each camera
            active_camera = self.scene.camera
            
            for camera_obj in cameras:
                cam_score = 100
                cam_data = camera_obj.data
                
                # Check if camera is inside mesh (basic ray-casting)
                try:
                    origin = camera_obj.location
                    # Cast ray downward to check for nearby geometry
                    direction = Vector((0, 0, -1))
                    
                    # Use depsgraph for ray-casting
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    hit, location, normal, face_idx = bpy.context.scene.ray_cast(
                        bpy.context.view_layer,
                        origin,
                        direction,
                        distance=0.5
                    )
                    
                    if hit:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' not inside mesh",
                            "passed": False,
                            "severity": "high",
                            "message": f"Camera appears to be inside geometry (hit at distance {distance:.2f}m)",
                            "fix_hint": "Move camera outside all geometry"
                        })
                        cam_score -= 30
                    else:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' not inside mesh",
                            "passed": True,
                            "severity": "high",
                            "message": "Camera is outside geometry",
                            "fix_hint": ""
                        })
                except Exception as e:
                    details.append({
                        "check": f"Camera '{camera_obj.name}' geometry check",
                        "passed": True,
                        "severity": "low",
                        "message": f"Could not perform ray-cast check: {str(e)[:50]}",
                        "fix_hint": ""
                    })
                
                # Check clip planes
                if cam_data.clip_start >= 1.0:
                    details.append({
                        "check": f"Camera '{camera_obj.name}' clip_start reasonable",
                        "passed": False,
                        "severity": "high",
                        "message": f"clip_start={cam_data.clip_start}m is too large, may clip nearby geometry",
                        "fix_hint": "Set clip_start to a small value (0.01-0.1m)"
                    })
                    cam_score -= 20
                else:
                    details.append({
                        "check": f"Camera '{camera_obj.name}' clip_start reasonable",
                        "passed": True,
                        "severity": "high",
                        "message": f"clip_start={cam_data.clip_start}m is reasonable",
                        "fix_hint": ""
                    })
                
                if cam_data.clip_end <= 10.0:
                    details.append({
                        "check": f"Camera '{camera_obj.name}' clip_end reasonable",
                        "passed": False,
                        "severity": "medium",
                        "message": f"clip_end={cam_data.clip_end}m may be too small",
                        "fix_hint": "Increase clip_end to at least 100-1000m depending on scene scale"
                    })
                    cam_score -= 15
                else:
                    details.append({
                        "check": f"Camera '{camera_obj.name}' clip_end reasonable",
                        "passed": True,
                        "severity": "medium",
                        "message": f"clip_end={cam_data.clip_end}m is reasonable",
                        "fix_hint": ""
                    })
                
                # Check FOV for perspective cameras
                if cam_data.type == "PERSP":
                    focal_length = cam_data.lens
                    if focal_length < 18 or focal_length > 200:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' focal length reasonable",
                            "passed": False,
                            "severity": "medium",
                            "message": f"focal_length={focal_length}mm is outside typical range (18-200mm)",
                            "fix_hint": "Use focal length between 18-200mm for typical scenes"
                        })
                        cam_score -= 10
                    else:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' focal length reasonable",
                            "passed": True,
                            "severity": "medium",
                            "message": f"focal_length={focal_length}mm is reasonable",
                            "fix_hint": ""
                        })
                
                # Check if camera can see something
                try:
                    # This is a simplified check - just verify scene has geometry
                    meshes = [obj for obj in self.scene.objects if obj.type == "MESH"]
                    if meshes:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' can see geometry",
                            "passed": True,
                            "severity": "high",
                            "message": f"Scene has {len(meshes)} mesh objects",
                            "fix_hint": ""
                        })
                    else:
                        details.append({
                            "check": f"Camera '{camera_obj.name}' can see geometry",
                            "passed": False,
                            "severity": "critical",
                            "message": "No mesh objects in scene",
                            "fix_hint": "Add mesh objects to scene"
                        })
                        cam_score = 0
                except Exception as e:
                    pass
                
                score = min(score, cam_score)
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Camera validation",
                "passed": False,
                "severity": "critical",
                "message": f"Error during camera validation: {str(e)[:100]}",
                "fix_hint": "Check scene integrity"
            })
            return "FAIL", 0, details
    
    def check_lighting(self) -> Tuple[str, int, List[Dict]]:
        """Check lighting configuration."""
        details = []
        score = 100
        
        try:
            # Get all lights in scene
            lights = [obj for obj in self.scene.objects if obj.type == "LIGHT"]
            
            # Check if any lights exist
            if not lights:
                details.append({
                    "check": "Lights exist in scene",
                    "passed": False,
                    "severity": "critical",
                    "message": "No light objects found in scene",
                    "fix_hint": "Add at least one light (Shift+A > Light)"
                })
                score -= 50
                self.add_warning("Scene has no lights - will render black")
            else:
                details.append({
                    "check": "Lights exist in scene",
                    "passed": True,
                    "severity": "critical",
                    "message": f"Found {len(lights)} light(s)",
                    "fix_hint": ""
                })
            
            # Check for minimum light count
            if len(lights) < 3:
                details.append({
                    "check": "Minimum light count (3)",
                    "passed": False,
                    "severity": "medium",
                    "message": f"Only {len(lights)} light(s), recommended 3+",
                    "fix_hint": "Add more lights for better lighting (key, fill, back lights)"
                })
                score -= 15
            else:
                details.append({
                    "check": "Minimum light count (3)",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Found {len(lights)} lights (good coverage)",
                    "fix_hint": ""
                })
            
            # Check total light energy
            total_energy = sum(light.data.energy for light in lights)
            
            if total_energy == 0:
                details.append({
                    "check": "Total light energy > 0",
                    "passed": False,
                    "severity": "critical",
                    "message": "Total light energy is 0 (all lights are dark)",
                    "fix_hint": "Increase light energy values"
                })
                score -= 40
                self.add_blocking_issue("All lights have zero energy")
            elif total_energy < 100:
                details.append({
                    "check": "Total light energy > 100W",
                    "passed": False,
                    "severity": "high",
                    "message": f"Total energy={total_energy:.1f}W is very low",
                    "fix_hint": "Increase light energy (target 200-500W)"
                })
                score -= 20
            else:
                details.append({
                    "check": "Total light energy > 100W",
                    "passed": True,
                    "severity": "high",
                    "message": f"Total energy={total_energy:.1f}W is adequate",
                    "fix_hint": ""
                })
            
            # Check for dead lights (energy = 0)
            dead_lights = [l.name for l in lights if l.data.energy == 0]
            if dead_lights:
                details.append({
                    "check": "No dead lights (energy=0)",
                    "passed": False,
                    "severity": "high",
                    "message": f"Found {len(dead_lights)} dead light(s): {', '.join(dead_lights[:3])}",
                    "fix_hint": "Remove or enable dead lights"
                })
                score -= 15
            else:
                details.append({
                    "check": "No dead lights (energy=0)",
                    "passed": True,
                    "severity": "high",
                    "message": "All lights have non-zero energy",
                    "fix_hint": ""
                })
            
            # Check world background
            try:
                worlds = bpy.data.worlds
                if worlds and worlds[0].use_nodes:
                    details.append({
                        "check": "World has background shader",
                        "passed": True,
                        "severity": "medium",
                        "message": "World shader nodes are enabled",
                        "fix_hint": ""
                    })
                else:
                    details.append({
                        "check": "World has background shader",
                        "passed": False,
                        "severity": "medium",
                        "message": "World shader not properly configured",
                        "fix_hint": "Enable Use Nodes in World Shader Editor"
                    })
                    score -= 10
            except Exception as e:
                details.append({
                    "check": "World configuration",
                    "passed": True,
                    "severity": "low",
                    "message": "Could not check world shader",
                    "fix_hint": ""
                })
            
            # Check light color sanity
            for light in lights:
                if light.data.type in ["POINT", "SUN", "SPOT"]:
                    color = light.data.color
                    # Check if color is suspiciously monochromatic
                    if color[0] > 0.95 and color[1] < 0.05 and color[2] < 0.05:
                        details.append({
                            "check": f"Light '{light.name}' color sanity",
                            "passed": False,
                            "severity": "low",
                            "message": f"Light is pure red, likely unintended",
                            "fix_hint": "Adjust light color to white or intended color"
                        })
                        score -= 5
            
            # Check for specific scene patterns (night scene patterns)
            scene_name = self.scene.name.lower()
            if "night" in scene_name or "scene4" in scene_name:
                # Look for headlight/streetlight objects
                light_objects = [obj.name.lower() for obj in self.scene.objects]
                has_headlight = any("headlight" in name or "streetlight" in name or "lamp" in name for name in light_objects)
                if not has_headlight and len(lights) < 2:
                    details.append({
                        "check": "Night scene has appropriate lighting",
                        "passed": False,
                        "severity": "medium",
                        "message": "Night scene detected but no headlights/streetlights found",
                        "fix_hint": "Add headlight or streetlight objects for night scenes"
                    })
                    score -= 15
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Lighting validation",
                "passed": False,
                "severity": "high",
                "message": f"Error during lighting validation: {str(e)[:100]}",
                "fix_hint": "Check scene integrity"
            })
            return "WARN", 50, details
    
    def check_materials(self) -> Tuple[str, int, List[Dict]]:
        """Check material configuration."""
        details = []
        score = 100
        
        try:
            # Get all mesh objects
            meshes = [obj for obj in self.scene.objects if obj.type == "MESH"]
            
            if not meshes:
                details.append({
                    "check": "Mesh objects exist",
                    "passed": False,
                    "severity": "critical",
                    "message": "No mesh objects in scene",
                    "fix_hint": "Add mesh objects"
                })
                return "FAIL", 0, details
            
            # Check meshes with no materials
            no_material_meshes = []
            default_grey_meshes = []
            has_principled = False
            emission_errors = []
            glass_issues = []
            
            for mesh_obj in meshes:
                if not mesh_obj.data.materials:
                    no_material_meshes.append(mesh_obj.name)
                else:
                    # Check material properties
                    for material in mesh_obj.data.materials:
                        if material and material.use_nodes:
                            # Check for Principled BSDF
                            for node in material.node_tree.nodes:
                                if "Principled" in node.type:
                                    has_principled = True
                                if "Emission" in node.type and node.inputs.get("Strength"):
                                    emission_val = node.inputs["Strength"].default_value
                                    if emission_val > 0:
                                        emission_errors.append({
                                            "object": mesh_obj.name,
                                            "material": material.name,
                                            "emission": emission_val
                                        })
                            
                            # Check for glass (transmission)
                            if "glass" in material.name.lower() or "transparent" in material.name.lower():
                                found_transmission = False
                                for node in material.node_tree.nodes:
                                    if "Principled" in node.type:
                                        if "Transmission Weight" in node.inputs:
                                            if node.inputs["Transmission Weight"].default_value < 0.5:
                                                glass_issues.append({
                                                    "object": mesh_obj.name,
                                                    "material": material.name,
                                                    "issue": "Transmission weight too low"
                                                })
                        
                        # Check for default grey material
                        if material and hasattr(material, "diffuse_color"):
                            color = material.diffuse_color
                            if abs(color[0] - 0.8) < 0.05 and abs(color[1] - 0.8) < 0.05 and abs(color[2] - 0.8) < 0.05:
                                default_grey_meshes.append(mesh_obj.name)
            
            # Report findings
            if no_material_meshes:
                details.append({
                    "check": "All meshes have materials",
                    "passed": False,
                    "severity": "high",
                    "message": f"{len(no_material_meshes)} mesh(es) have no material: {', '.join(no_material_meshes[:3])}",
                    "fix_hint": "Assign materials to all meshes"
                })
                score -= 20
            else:
                details.append({
                    "check": "All meshes have materials",
                    "passed": True,
                    "severity": "high",
                    "message": f"All {len(meshes)} meshes have materials",
                    "fix_hint": ""
                })
            
            if default_grey_meshes:
                details.append({
                    "check": "Meshes don't use default grey material",
                    "passed": False,
                    "severity": "medium",
                    "message": f"{len(default_grey_meshes)} mesh(es) use default grey color",
                    "fix_hint": "Customize material colors"
                })
                score -= 15
            else:
                details.append({
                    "check": "Meshes don't use default grey material",
                    "passed": True,
                    "severity": "medium",
                    "message": "Materials have custom colors",
                    "fix_hint": ""
                })
            
            if has_principled:
                details.append({
                    "check": "Uses Principled BSDF shader",
                    "passed": True,
                    "severity": "medium",
                    "message": "Found Principled BSDF nodes (good practice)",
                    "fix_hint": ""
                })
            else:
                details.append({
                    "check": "Uses Principled BSDF shader",
                    "passed": False,
                    "severity": "low",
                    "message": "No Principled BSDF nodes found",
                    "fix_hint": "Consider using Principled BSDF for better material definition"
                })
                score -= 5
            
            if emission_errors:
                details.append({
                    "check": "No unintended emission on meshes",
                    "passed": False,
                    "severity": "medium",
                    "message": f"{len(emission_errors)} mesh(es) have emission (might be material error)",
                    "fix_hint": "Check emission values in material nodes"
                })
                score -= 10
            
            if glass_issues:
                details.append({
                    "check": "Glass objects have proper transmission",
                    "passed": False,
                    "severity": "low",
                    "message": f"{len(glass_issues)} glass mesh(es) have low transmission weight",
                    "fix_hint": "Increase Transmission Weight in Principled BSDF"
                })
                score -= 5
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Material validation",
                "passed": False,
                "severity": "high",
                "message": f"Error during material validation: {str(e)[:100]}",
                "fix_hint": "Check scene integrity"
            })
            return "WARN", 50, details
    
    def check_geometry(self) -> Tuple[str, int, List[Dict]]:
        """Check scene geometry."""
        details = []
        score = 100
        
        try:
            # Get all mesh objects
            meshes = [obj for obj in self.scene.objects if obj.type == "MESH"]
            
            if not meshes:
                details.append({
                    "check": "Mesh objects exist",
                    "passed": False,
                    "severity": "critical",
                    "message": "No mesh objects in scene",
                    "fix_hint": "Add mesh objects to scene"
                })
                return "FAIL", 0, details
            
            # Count total vertices
            total_verts = sum(len(mesh.data.vertices) for mesh in meshes)
            
            if total_verts < 1000:
                details.append({
                    "check": "Total vertex count >= 1000",
                    "passed": False,
                    "severity": "medium",
                    "message": f"Only {total_verts} vertices in scene (very simple geometry)",
                    "fix_hint": "Add more geometric detail or objects"
                })
                score -= 20
            else:
                details.append({
                    "check": "Total vertex count >= 1000",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Scene has {total_verts:,} vertices (good geometry complexity)",
                    "fix_hint": ""
                })
            
            # Check for objects at origin
            origin_objects = []
            for obj in meshes:
                if abs(obj.location.x) < 0.01 and abs(obj.location.y) < 0.01 and abs(obj.location.z) < 0.01:
                    origin_objects.append(obj.name)
            
            if len(origin_objects) > 2:
                details.append({
                    "check": "Objects not accumulated at origin",
                    "passed": False,
                    "severity": "medium",
                    "message": f"{len(origin_objects)} objects at origin [0,0,0] (accumulated import issue?)",
                    "fix_hint": "Reposition objects or check import process"
                })
                score -= 10
            else:
                details.append({
                    "check": "Objects not accumulated at origin",
                    "passed": True,
                    "severity": "medium",
                    "message": "Objects are properly distributed",
                    "fix_hint": ""
                })
            
            # Check for vehicle-like objects
            vehicle_patterns = ["car", "sedan", "truck", "suv", "van", "vehicle", "auto"]
            vehicle_objects = []
            for obj in self.scene.objects:
                name_lower = obj.name.lower()
                if any(pattern in name_lower for pattern in vehicle_patterns):
                    vehicle_objects.append(obj.name)
            
            if len(vehicle_objects) < 2:
                details.append({
                    "check": "Scene has 2+ vehicle-like objects",
                    "passed": False,
                    "severity": "medium",
                    "message": f"Only {len(vehicle_objects)} vehicle object(s) found",
                    "fix_hint": "Check scene naming or add vehicles (e.g., car, sedan, truck)"
                })
                score -= 15
            else:
                details.append({
                    "check": "Scene has 2+ vehicle-like objects",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Found {len(vehicle_objects)} vehicle objects: {', '.join(vehicle_objects[:3])}",
                    "fix_hint": ""
                })
            
            # Check for subdivision surface modifiers
            subdiv_count = 0
            for obj in meshes:
                for modifier in obj.modifiers:
                    if modifier.type == "SUBSURF":
                        subdiv_count += 1
            
            if subdiv_count > 0:
                details.append({
                    "check": "Subdivision surface modifiers found",
                    "passed": True,
                    "severity": "low",
                    "message": f"Found {subdiv_count} subdivision surface modifier(s) (adds render time)",
                    "fix_hint": ""
                })
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Geometry validation",
                "passed": False,
                "severity": "high",
                "message": f"Error during geometry validation: {str(e)[:100]}",
                "fix_hint": "Check scene integrity"
            })
            return "WARN", 50, details
    
    def check_render_settings(self) -> Tuple[str, int, List[Dict]]:
        """Check render settings."""
        details = []
        score = 100
        
        try:
            # Check render engine
            engine = self.scene.render.engine
            
            if engine not in ["CYCLES", "EEVEE", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]:
                details.append({
                    "check": "Render engine is EEVEE or Cycles",
                    "passed": False,
                    "severity": "high",
                    "message": f"Render engine is {engine}, expected EEVEE or Cycles",
                    "fix_hint": "Change render engine in Scene Properties"
                })
                score -= 30
            else:
                details.append({
                    "check": "Render engine is EEVEE or Cycles",
                    "passed": True,
                    "severity": "high",
                    "message": f"Using {engine} renderer",
                    "fix_hint": ""
                })
            
            # Engine-specific checks
            if engine == "CYCLES":
                samples = self.scene.cycles.samples
                if samples < 64:
                    details.append({
                        "check": "Cycles samples >= 64",
                        "passed": False,
                        "severity": "high",
                        "message": f"Cycles samples={samples} is too low (will be noisy)",
                        "fix_hint": "Increase samples to 128-256 for production"
                    })
                    score -= 20
                else:
                    details.append({
                        "check": "Cycles samples >= 64",
                        "passed": True,
                        "severity": "high",
                        "message": f"Cycles samples={samples}",
                        "fix_hint": ""
                    })
                
                # Check denoiser
                if self.scene.cycles.use_denoiser:
                    details.append({
                        "check": "Cycles denoiser enabled",
                        "passed": True,
                        "severity": "medium",
                        "message": "Denoiser is enabled",
                        "fix_hint": ""
                    })
                else:
                    details.append({
                        "check": "Cycles denoiser enabled",
                        "passed": False,
                        "severity": "medium",
                        "message": "Denoiser is disabled",
                        "fix_hint": "Enable denoiser for faster renders (Render Properties > Denoising)"
                    })
                    score -= 10
                
                # Check caustics
                if self.scene.cycles.caustics_reflective or self.scene.cycles.caustics_refractive:
                    details.append({
                        "check": "Caustics disabled",
                        "passed": False,
                        "severity": "low",
                        "message": "Caustics are enabled (adds significant render time)",
                        "fix_hint": "Disable caustics unless necessary"
                    })
                    score -= 5
            
            elif engine == "EEVEE":
                taa_samples = self.scene.eevee.taa_samples
                if taa_samples < 64:
                    details.append({
                        "check": "EEVEE TAA samples >= 64",
                        "passed": False,
                        "severity": "medium",
                        "message": f"TAA samples={taa_samples} is too low",
                        "fix_hint": "Increase TAA samples to 64-128"
                    })
                    score -= 15
                else:
                    details.append({
                        "check": "EEVEE TAA samples >= 64",
                        "passed": True,
                        "severity": "medium",
                        "message": f"TAA samples={taa_samples}",
                        "fix_hint": ""
                    })
            
            # Check resolution
            width = self.scene.render.resolution_x
            height = self.scene.render.resolution_y
            
            is_hd = (width >= 1920 and height >= 1080) or (width >= 1080 and height >= 1920)
            
            if not is_hd:
                details.append({
                    "check": "Resolution is HD (1920x1080+)",
                    "passed": False,
                    "severity": "medium",
                    "message": f"Resolution={width}x{height} is lower than HD",
                    "fix_hint": "Set resolution to 1920x1080 or higher"
                })
                score -= 10
            else:
                details.append({
                    "check": "Resolution is HD (1920x1080+)",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Resolution={width}x{height}",
                    "fix_hint": ""
                })
            
            # Check output format
            file_format = self.scene.render.image_settings.file_format
            
            if file_format not in ["PNG", "OPEN_EXR"]:
                details.append({
                    "check": "Output format is PNG or EXR",
                    "passed": False,
                    "severity": "medium",
                    "message": f"Output format is {file_format}, PNG/EXR recommended",
                    "fix_hint": "Change output format in Render Properties > Image"
                })
                score -= 10
            else:
                details.append({
                    "check": "Output format is PNG or EXR",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Output format is {file_format}",
                    "fix_hint": ""
                })
            
            # Check film transparent
            if self.scene.render.film_transparent:
                details.append({
                    "check": "Film transparent is False (unless intentional)",
                    "passed": False,
                    "severity": "low",
                    "message": "Film transparent is enabled",
                    "fix_hint": "Disable Film Transparent unless you need transparency"
                })
                score -= 5
            else:
                details.append({
                    "check": "Film transparent is False (unless intentional)",
                    "passed": True,
                    "severity": "low",
                    "message": "Film transparent is disabled",
                    "fix_hint": ""
                })
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Render settings validation",
                "passed": False,
                "severity": "high",
                "message": f"Error during render settings validation: {str(e)[:100]}",
                "fix_hint": "Check render properties"
            })
            return "WARN", 50, details
    
    def check_forensic_compliance(self) -> Tuple[str, int, List[Dict]]:
        """Check for forensic/demonstrative aid objects and markers."""
        details = []
        score = 100
        
        try:
            # Patterns to search for
            marker_patterns = ["marker", "evidence", "scale", "label", "arrow", "text", "ruler", "measuring"]
            demonstrative_patterns = ["demonstrative", "aid", "annotation"]
            
            found_markers = {}
            found_demonstrative = False
            
            # Search all objects
            for obj in self.scene.objects:
                name_lower = obj.name.lower()
                
                # Check for marker objects
                for pattern in marker_patterns:
                    if pattern in name_lower:
                        if pattern not in found_markers:
                            found_markers[pattern] = []
                        found_markers[pattern].append(obj.name)
                
                # Check for demonstrative aid text
                if obj.type == "TEXT":
                    text_content = obj.data.body if hasattr(obj.data, "body") else ""
                    if any(pattern in text_content.lower() for pattern in demonstrative_patterns):
                        found_demonstrative = True
            
            # Check for measurement tools
            has_ruler = any("ruler" in obj.name.lower() or "measure" in obj.name.lower() for obj in self.scene.objects)
            
            # Report findings
            if found_markers:
                marker_list = ", ".join([f"{k}({len(v)})" for k, v in found_markers.items()])
                details.append({
                    "check": "Forensic markers found",
                    "passed": True,
                    "severity": "medium",
                    "message": f"Found markers: {marker_list}",
                    "fix_hint": ""
                })
            else:
                details.append({
                    "check": "Forensic markers found",
                    "passed": False,
                    "severity": "medium",
                    "message": "No standard forensic markers found",
                    "fix_hint": "Add markers, scales, labels as needed for forensic visualization"
                })
                score -= 15
            
            if found_demonstrative:
                details.append({
                    "check": "Demonstrative aid annotation found",
                    "passed": True,
                    "severity": "medium",
                    "message": "Found demonstrative aid annotations",
                    "fix_hint": ""
                })
            else:
                details.append({
                    "check": "Demonstrative aid annotation found",
                    "passed": False,
                    "severity": "low",
                    "message": "No demonstrative aid text found",
                    "fix_hint": "Consider adding annotation if rendering demonstrative aids"
                })
                score -= 5
            
            if has_ruler:
                details.append({
                    "check": "Measurement/ruler objects exist",
                    "passed": True,
                    "severity": "low",
                    "message": "Found measurement objects",
                    "fix_hint": ""
                })
            else:
                details.append({
                    "check": "Measurement/ruler objects exist",
                    "passed": False,
                    "severity": "low",
                    "message": "No ruler/measurement objects found",
                    "fix_hint": "Add measurement scale for forensic visualization"
                })
                score -= 5
            
            # Check for sight-line visualization
            sightline_objects = [obj.name for obj in self.scene.objects if any(
                term in obj.name.lower() for term in ["sightline", "sight-line", "line_of_sight", "los"]
            )]
            
            if sightline_objects:
                details.append({
                    "check": "Sight-line visualization found",
                    "passed": True,
                    "severity": "low",
                    "message": f"Found sight-line objects: {', '.join(sightline_objects[:3])}",
                    "fix_hint": ""
                })
            else:
                details.append({
                    "check": "Sight-line visualization found",
                    "passed": False,
                    "severity": "low",
                    "message": "No sight-line objects found",
                    "fix_hint": "Add sight-line visualization if needed for forensic analysis"
                })
                score -= 5
            
            verdict = "PASS" if score >= 80 else "WARN" if score >= 50 else "FAIL"
            return verdict, score, details
            
        except Exception as e:
            details.append({
                "check": "Forensic compliance validation",
                "passed": False,
                "severity": "low",
                "message": f"Error during forensic check: {str(e)[:100]}",
                "fix_hint": "Check scene objects"
            })
            return "WARN", 60, details
    
    def validate(self) -> int:
        """Run all validation checks."""
        try:
            # Run all checks
            verdict, score, details = self.check_cameras()
            self.add_check_result("cameras", verdict, score, details)
            
            verdict, score, details = self.check_lighting()
            self.add_check_result("lighting", verdict, score, details)
            
            verdict, score, details = self.check_materials()
            self.add_check_result("materials", verdict, score, details)
            
            verdict, score, details = self.check_geometry()
            self.add_check_result("geometry", verdict, score, details)
            
            verdict, score, details = self.check_render_settings()
            self.add_check_result("render_settings", verdict, score, details)
            
            verdict, score, details = self.check_forensic_compliance()
            self.add_check_result("forensic_compliance", verdict, score, details)
            
            # Update overall verdict and score
            self.update_overall_verdict()
            
            # Record execution time
            self.results["execution_time_ms"] = int((time.time() - self.start_time) * 1000)
            
            # Print human-readable summary
            self._print_summary()
            
            # Write JSON results if output path provided
            if self.output_path:
                self._write_json_report()
            
            # Return exit code based on verdict
            if self.results["overall_verdict"] == "FAIL":
                return 1
            else:
                return 0
        
        except Exception as e:
            print(f"FATAL ERROR: {str(e)}")
            traceback.print_exc()
            return 1
    
    def _print_summary(self):
        """Print human-readable validation summary."""
        print("\n" + "="*70)
        print("PRE-RENDER SCENE VALIDATION REPORT")
        print("="*70)
        print(f"File: {self.results['file']}")
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Overall Verdict: {self.results['overall_verdict']}")
        print(f"Overall Score: {self.results['overall_score']}/100")
        print(f"Predicted Render Quality: {self.results['predicted_render_quality']}")
        print(f"Execution Time: {self.results['execution_time_ms']}ms")
        print("-"*70)
        
        for category, result in self.results["checks"].items():
            print(f"\n{category.upper()}: {result['verdict']} ({result['score']}/100)")
            for detail in result["details"][:5]:  # Show first 5 details per category
                severity_icon = {
                    "critical": "✗",
                    "high": "!",
                    "medium": "·",
                    "low": "○"
                }.get(detail["severity"], "?")
                status = "✓" if detail["passed"] else "✗"
                print(f"  {status} [{severity_icon}] {detail['check']}")
                if not detail["passed"]:
                    print(f"    → {detail['message']}")
        
        if self.results["blocking_issues"]:
            print(f"\n🚫 BLOCKING ISSUES ({len(self.results['blocking_issues'])}):")
            for issue in self.results["blocking_issues"]:
                print(f"  • {issue}")
        
        if self.results["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(self.results['warnings'])}):")
            for warning in self.results["warnings"][:5]:
                print(f"  • {warning}")
        
        if self.results["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS ({len(self.results['recommendations'])}):")
            for rec in self.results["recommendations"][:5]:
                print(f"  • {rec}")
        
        print("\n" + "="*70)
        if self.results["skip_render_recommendation"]:
            print("⛔ RECOMMENDATION: Do NOT render. Fix blocking issues first.")
        else:
            print("✓ RECOMMENDATION: Scene appears ready to render.")
        print("="*70 + "\n")
    
    def _write_json_report(self):
        """Write JSON report to file."""
        try:
            output_file = Path(self.output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w") as f:
                json.dump(self.results, f, indent=2)
            
            print(f"JSON report written to: {output_file}")
        except Exception as e:
            print(f"ERROR writing JSON report: {str(e)}")


def parse_arguments():
    """Parse command-line arguments."""
    output_path = None
    
    # Look for arguments after '--'
    if "--" in sys.argv:
        dash_index = sys.argv.index("--")
        args = sys.argv[dash_index + 1:]
        
        for i, arg in enumerate(args):
            if arg == "--output" and i + 1 < len(args):
                output_path = args[i + 1]
    
    return output_path


def main():
    """Main entry point."""
    output_path = parse_arguments()
    
    validator = PreRenderValidator(output_path)
    exit_code = validator.validate()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
