def handle_forensic_scene(params):
    """Build courtroom-ready forensic/litigation scene reconstructions.
    Constructs road scenes, places vehicles, human figures, annotations,
    camera rigs, and lighting for legal demonstrative animations.

    Actions:
      build_road        — Create road segments, intersections, lane markings
      place_vehicle     — Add a vehicle (sedan, SUV, truck, motorcycle, bicycle, pedestrian)
      place_figure      — Add a human figure (standing, walking, sitting)
      add_annotation    — Text labels, speed indicators, distance markers, trajectory arrows
      setup_cameras     — Bird's eye, driver POV, witness POV, orbit rig
      set_time_of_day   — Lighting for day, night, dusk, dawn
      animate_vehicle   — Keyframe a vehicle along a path with speed
      add_impact_marker — Skid marks, debris field, impact point indicator
      ghost_scenario    — Semi-transparent "what-if" overlay vehicle
      build_full_scene  — Complete scene from a structured description
    """
    action = params.get("action", "build_road")
    scene = bpy.context.scene

    # ── Utility: create a simple box-shaped vehicle ──
    def _create_vehicle(name, vehicle_type, location, rotation_deg, color):
        """Create a simplified vehicle mesh appropriate for forensic demos."""
        dims = {
            "sedan":      (4.5, 1.8, 1.4),
            "suv":        (4.8, 2.0, 1.8),
            "truck":      (6.0, 2.4, 2.5),
            "pickup":     (5.5, 2.0, 1.9),
            "van":        (5.0, 2.0, 2.2),
            "motorcycle": (2.2, 0.8, 1.2),
            "bicycle":    (1.8, 0.6, 1.1),
            "bus":        (12.0, 2.5, 3.2),
            "semi":       (16.0, 2.5, 4.0),
        }
        d = dims.get(vehicle_type.lower(), (4.5, 1.8, 1.4))

        # Body
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        body = bpy.context.active_object
        body.name = name
        body.scale = (d[0], d[1], d[2] * 0.6)
        body.location[2] = location[2] + d[2] * 0.3
        if rotation_deg:
            body.rotation_euler[2] = math.radians(rotation_deg)

        # Cabin (upper portion) for cars/trucks
        if vehicle_type.lower() not in ("motorcycle", "bicycle"):
            bpy.ops.mesh.primitive_cube_add(size=1, location=location)
            cabin = bpy.context.active_object
            cabin.name = f"{name}_Cabin"
            cabin.scale = (d[0] * 0.6, d[1] * 0.95, d[2] * 0.45)
            cabin.location[2] = location[2] + d[2] * 0.75
            if rotation_deg:
                cabin.rotation_euler[2] = math.radians(rotation_deg)
            cabin.parent = body
            cabin.location = (d[0] * 0.05, 0, d[2] * 0.45 / (d[2] * 0.6))

        # Wheels (4 cylinders)
        wheel_positions = [
            (d[0] * 0.35, d[1] * 0.5, -d[2] * 0.2),
            (d[0] * 0.35, -d[1] * 0.5, -d[2] * 0.2),
            (-d[0] * 0.35, d[1] * 0.5, -d[2] * 0.2),
            (-d[0] * 0.35, -d[1] * 0.5, -d[2] * 0.2),
        ]
        if vehicle_type.lower() in ("motorcycle", "bicycle"):
            wheel_positions = [
                (d[0] * 0.4, 0, -d[2] * 0.2),
                (-d[0] * 0.4, 0, -d[2] * 0.2),
            ]
        for i, wp in enumerate(wheel_positions):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.25, location=location)
            wheel = bpy.context.active_object
            wheel.name = f"{name}_Wheel{i}"
            wheel.rotation_euler[0] = math.radians(90)
            wheel.parent = body
            wheel.location = wp
            wmat = bpy.data.materials.new(name=f"{name}_WheelMat{i}")
            wmat.use_nodes = True
            wmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
            wheel.data.materials.append(wmat)

        # Body material
        mat = bpy.data.materials.new(name=f"{name}_BodyMat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = 0.6
        bsdf.inputs["Roughness"].default_value = 0.3
        body.data.materials.append(mat)

        # Cabin glass
        if vehicle_type.lower() not in ("motorcycle", "bicycle"):
            gmat = bpy.data.materials.new(name=f"{name}_GlassMat")
            gmat.use_nodes = True
            gbsdf = gmat.node_tree.nodes["Principled BSDF"]
            gbsdf.inputs["Base Color"].default_value = (0.1, 0.15, 0.2, 1)
            gbsdf.inputs["Metallic"].default_value = 0.0
            gbsdf.inputs["Roughness"].default_value = 0.1
            gbsdf.inputs["Alpha"].default_value = 0.4
            for child in body.children:
                if "Cabin" in child.name:
                    child.data.materials.append(gmat)

        return body

    def _create_figure(name, location, rotation_deg=0, color=(0.7, 0.5, 0.3, 1)):
        """Create a simple stylized human figure for forensic scenes."""
        bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1], location[2] + 0.9))
        torso = bpy.context.active_object
        torso.name = name
        torso.scale = (0.35, 0.2, 0.5)
        if rotation_deg:
            torso.rotation_euler[2] = math.radians(rotation_deg)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0, 0, 0))
        head = bpy.context.active_object
        head.name = f"{name}_Head"
        head.parent = torso
        head.location = (0, 0, 0.5)

        for side, y_off in [("L", 0.08), ("R", -0.08)]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
            leg = bpy.context.active_object
            leg.name = f"{name}_Leg{side}"
            leg.scale = (0.12, 0.12, 0.45)
            leg.parent = torso
            leg.location = (0, y_off, -0.7)

        for side, y_off in [("L", 0.3), ("R", -0.3)]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
            arm = bpy.context.active_object
            arm.name = f"{name}_Arm{side}"
            arm.scale = (0.1, 0.1, 0.4)
            arm.parent = torso
            arm.location = (0, y_off, 0.05)

        mat = bpy.data.materials.new(name=f"{name}_Mat")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
        torso.data.materials.append(mat)
        return torso

    # ── ACTION: build_road ──
    if action == "build_road":
        road_type = params.get("road_type", "straight")
        lanes = params.get("lanes", 2)
        length = params.get("length", 40)
        location = params.get("location", [0, 0, 0])
        lane_width = 3.7
        width = params.get("width", lane_width * lanes + 1.0)

        if road_type == "straight":
            bpy.ops.mesh.primitive_plane_add(size=1, location=location)
            road = bpy.context.active_object
            road.name = params.get("name", "Road")
            road.scale = (length, width, 1)
            mat = bpy.data.materials.new(name="Asphalt")
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.15, 0.15, 0.15, 1)
            mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
            road.data.materials.append(mat)

            bpy.ops.mesh.primitive_plane_add(size=1, location=(location[0], location[1], location[2] + 0.01))
            cl = bpy.context.active_object
            cl.name = "CenterLine"
            cl.scale = (length, 0.1, 1)
            lmat = bpy.data.materials.new(name="YellowLine")
            lmat.use_nodes = True
            lmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.85, 0, 1)
            cl.data.materials.append(lmat)

            for side, y_off in [("Left", width + 1), ("Right", -(width + 1))]:
                bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1] + y_off, location[2] + 0.08))
                sw = bpy.context.active_object
                sw.name = f"Sidewalk_{side}"
                sw.scale = (length, 1.5, 0.15)
                swmat = bpy.data.materials.new(name=f"Concrete_{side}")
                swmat.use_nodes = True
                swmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.6, 0.58, 0.55, 1)
                sw.data.materials.append(swmat)

            return {"road": "Road", "type": road_type, "lanes": lanes, "length": length, "width": width,
                    "elements": ["Road", "CenterLine", "Sidewalk_Left", "Sidewalk_Right"]}

        if road_type == "intersection":
            created = []
            mat = bpy.data.materials.new(name="Asphalt_Main")
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.15, 0.15, 0.15, 1)
            mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9

            bpy.ops.mesh.primitive_plane_add(size=1, location=location)
            main = bpy.context.active_object
            main.name = "Road_Main"
            main.scale = (length, width, 1)
            main.data.materials.append(mat)
            created.append("Road_Main")

            cross_length = params.get("cross_length", length)
            bpy.ops.mesh.primitive_plane_add(size=1, location=location)
            cross = bpy.context.active_object
            cross.name = "Road_Cross"
            cross.scale = (width, cross_length, 1)
            cross.data.materials.append(mat)
            created.append("Road_Cross")

            stripe_mat = bpy.data.materials.new(name="WhiteStripe")
            stripe_mat.use_nodes = True
            stripe_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)

            for ci, (cx, cy, sx, sy) in enumerate([
                (width + 1, 0, 0.8, width), (-(width + 1), 0, 0.8, width),
                (0, width + 1, width, 0.8), (0, -(width + 1), width, 0.8),
            ]):
                bpy.ops.mesh.primitive_plane_add(size=1, location=(location[0]+cx, location[1]+cy, location[2]+0.01))
                cw = bpy.context.active_object
                cw.name = f"Crosswalk_{ci}"
                cw.scale = (sx, sy, 1)
                cw.data.materials.append(stripe_mat)
                created.append(f"Crosswalk_{ci}")

            return {"road": "Intersection", "type": road_type, "lanes": lanes, "elements": created}

        return {"error": f"Road type '{road_type}' not yet implemented. Use 'straight' or 'intersection'."}

    # ── ACTION: place_vehicle ──
    if action == "place_vehicle":
        name = params.get("name", "Vehicle")
        vehicle_type = params.get("vehicle_type", "sedan")
        location = params.get("location", [0, 0, 0])
        rotation = params.get("rotation", 0)
        color = params.get("color", [0.2, 0.3, 0.8, 1])
        label = params.get("label", None)
        damaged = params.get("damaged", False)

        veh = _create_vehicle(name, vehicle_type, location, rotation, color)

        if damaged:
            impact_side = params.get("impact_side", "front")
            offsets = {"front": (2.5, 0, 0.5), "rear": (-2.5, 0, 0.5), "left": (0, 1.2, 0.5), "right": (0, -1.2, 0.5)}
            off = offsets.get(impact_side, (2.5, 0, 0.5))
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=location)
            dmg = bpy.context.active_object
            dmg.name = f"{name}_DamageZone"
            dmg.parent = veh
            dmg.location = off
            dmat = bpy.data.materials.new(name=f"{name}_DamageMat")
            dmat.use_nodes = True
            dmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 0.5)
            dmat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.4
            dmg.data.materials.append(dmat)

        if label:
            bpy.ops.object.text_add(location=(location[0], location[1], location[2] + 3.5))
            txt = bpy.context.active_object
            txt.name = f"{name}_Label"
            txt.data.body = label
            txt.data.size = 0.8
            txt.data.align_x = "CENTER"
            txt.rotation_euler = (math.radians(90), 0, 0)

        return {"vehicle": name, "type": vehicle_type, "location": list(veh.location), "rotation": rotation}

    # ── ACTION: place_figure ──
    if action == "place_figure":
        name = params.get("name", "Person")
        location = params.get("location", [0, 0, 0])
        rotation = params.get("rotation", 0)
        color = params.get("color", [0.7, 0.5, 0.3, 1])
        label = params.get("label", None)
        fig = _create_figure(name, location, rotation, color=color)
        if label:
            bpy.ops.object.text_add(location=(location[0], location[1], location[2] + 2.2))
            txt = bpy.context.active_object
            txt.name = f"{name}_Label"
            txt.data.body = label
            txt.data.size = 0.5
            txt.data.align_x = "CENTER"
            txt.rotation_euler = (math.radians(90), 0, 0)
        return {"figure": name, "location": location}

    # ── ACTION: add_annotation ──
    if action == "add_annotation":
        ann_type = params.get("annotation_type", "label")
        text = params.get("text", "")
        location = params.get("location", [0, 0, 3])
        size = params.get("size", 1.0)
        color = params.get("color", [1, 1, 1, 1])

        if ann_type in ("label", "speed", "distance"):
            bpy.ops.object.text_add(location=location)
            txt = bpy.context.active_object
            txt.name = params.get("name", f"Annotation_{ann_type}")
            txt.data.body = text
            txt.data.size = size
            txt.data.align_x = "CENTER"
            txt.rotation_euler = (math.radians(90), 0, params.get("text_rotation", 0))
            mat = bpy.data.materials.new(name=f"{txt.name}_Mat")
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
            mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0
            txt.data.materials.append(mat)
            return {"annotation": txt.name, "type": ann_type, "text": text}

        if ann_type == "arrow":
            start = params.get("start", [0, 0, 0.1])
            end = params.get("end", [5, 0, 0.1])
            mid = [(s+e)/2 for s, e in zip(start, end)]
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = math.sqrt(dx*dx + dy*dy)
            angle = math.atan2(dy, dx)

            bpy.ops.mesh.primitive_cube_add(size=1, location=mid)
            shaft = bpy.context.active_object
            shaft.name = params.get("name", "Arrow")
            shaft.scale = (length * 0.45, 0.08, 0.04)
            shaft.rotation_euler[2] = angle

            bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.5, location=end)
            head = bpy.context.active_object
            head.name = f"{shaft.name}_Head"
            head.rotation_euler = (0, math.radians(-90), angle)
            head.parent = shaft
            head.location = (length * 0.48, 0, 0)

            amat = bpy.data.materials.new(name=f"{shaft.name}_Mat")
            amat.use_nodes = True
            amat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
            amat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 3.0
            shaft.data.materials.append(amat)
            head.data.materials.append(amat)
            return {"arrow": shaft.name, "start": start, "end": end, "length": length}

        return {"error": f"Unknown annotation type: {ann_type}"}

    # ── ACTION: setup_cameras ──
    if action == "setup_cameras":
        cam_type = params.get("camera_type", "bird_eye")
        target = params.get("target", [0, 0, 0])
        cameras = []

        if cam_type in ("bird_eye", "all"):
            height = params.get("height", 30)
            bpy.ops.object.camera_add(location=(target[0], target[1], height))
            cam = bpy.context.active_object
            cam.name = "Cam_BirdEye"
            cam.rotation_euler = (0, 0, 0)
            cam.data.lens = 24
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = params.get("ortho_scale", 50)
            cameras.append("Cam_BirdEye")

        if cam_type in ("driver_pov", "all"):
            driver_loc = params.get("driver_location", [0, 0, 1.5])
            driver_rot = params.get("driver_rotation", [80, 0, 90])
            bpy.ops.object.camera_add(location=driver_loc)
            cam = bpy.context.active_object
            cam.name = "Cam_DriverPOV"
            cam.rotation_euler = [math.radians(r) for r in driver_rot]
            cam.data.lens = 50
            driver_vehicle = params.get("driver_vehicle")
            if driver_vehicle:
                veh = bpy.data.objects.get(driver_vehicle)
                if veh:
                    cam.parent = veh
                    cam.location = (0, 0, 1.3)
            cameras.append("Cam_DriverPOV")

        if cam_type in ("witness", "all"):
            witness_loc = params.get("witness_location", [15, 15, 1.7])
            bpy.ops.object.camera_add(location=witness_loc)
            cam = bpy.context.active_object
            cam.name = "Cam_Witness"
            dx = target[0] - witness_loc[0]
            dy = target[1] - witness_loc[1]
            dz = target[2] - witness_loc[2]
            cam.rotation_euler = (math.atan2(math.sqrt(dx*dx + dy*dy), -dz), 0, math.atan2(dx, -dy))
            cam.data.lens = 35
            cameras.append("Cam_Witness")

        if cam_type in ("orbit", "all"):
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=target)
            pivot = bpy.context.active_object
            pivot.name = "CamOrbit_Pivot"
            orbit_dist = params.get("orbit_distance", 20)
            orbit_height = params.get("orbit_height", 10)
            bpy.ops.object.camera_add(location=(target[0] + orbit_dist, target[1], orbit_height))
            cam = bpy.context.active_object
            cam.name = "Cam_Orbit"
            cam.data.lens = 35
            track = cam.constraints.new("TRACK_TO")
            track.target = pivot
            track.track_axis = "TRACK_NEGATIVE_Z"
            track.up_axis = "UP_Y"
            frames = params.get("orbit_frames", 240)
            pivot.rotation_euler = (0, 0, 0)
            pivot.keyframe_insert(data_path="rotation_euler", frame=1)
            pivot.rotation_euler = (0, 0, math.radians(360))
            pivot.keyframe_insert(data_path="rotation_euler", frame=frames)
            # Set linear interpolation (Blender 5.x: fcurves moved to layered actions)
            try:
                if pivot.animation_data and pivot.animation_data.action:
                    action = pivot.animation_data.action
                    if hasattr(action, "fcurves"):
                        for fc in action.fcurves:
                            for kp in fc.keyframe_points:
                                kp.interpolation = "LINEAR"
            except Exception:
                pass  # Non-critical: orbit will still work with default interpolation
            cam.parent = pivot
            cam.location = (orbit_dist, 0, orbit_height)
            cameras.append("Cam_Orbit")

        if cameras:
            scene.camera = bpy.data.objects.get(cameras[0])
        return {"cameras": cameras, "active": cameras[0] if cameras else None}

    # ── ACTION: animate_vehicle ──
    if action == "animate_vehicle":
        veh_name = params.get("vehicle_name")
        veh = bpy.data.objects.get(veh_name)
        if not veh:
            return {"error": f"Vehicle '{veh_name}' not found"}
        waypoints = params.get("waypoints", [])
        for wp in waypoints:
            frame = wp.get("frame", 1)
            scene.frame_set(frame)
            if "location" in wp:
                veh.location = wp["location"]
                veh.keyframe_insert(data_path="location", frame=frame)
            if "rotation" in wp:
                veh.rotation_euler[2] = math.radians(wp["rotation"])
                veh.keyframe_insert(data_path="rotation_euler", frame=frame)
        return {"vehicle": veh_name, "keyframes": len(waypoints)}

    # ── ACTION: add_impact_marker ──
    if action == "add_impact_marker":
        marker_type = params.get("marker_type", "impact_point")
        location = params.get("location", [0, 0, 0])

        if marker_type == "impact_point":
            bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=0.08,
                                              location=(location[0], location[1], location[2] + 0.05))
            ring = bpy.context.active_object
            ring.name = params.get("name", "ImpactPoint")
            rmat = bpy.data.materials.new(name=f"{ring.name}_Mat")
            rmat.use_nodes = True
            rmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0, 0, 1)
            rmat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 5.0
            ring.data.materials.append(rmat)
            return {"marker": ring.name, "type": "impact_point"}

        if marker_type == "skid_mark":
            start = params.get("start", [0, 0, 0.01])
            end = params.get("end", [10, 0, 0.01])
            mid = [(s+e)/2 for s, e in zip(start, end)]
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = math.sqrt(dx*dx + dy*dy)
            angle = math.atan2(dy, dx)
            bpy.ops.mesh.primitive_plane_add(size=1, location=mid)
            skid = bpy.context.active_object
            skid.name = params.get("name", "SkidMark")
            skid.scale = (length/2, params.get("skid_width", 0.25), 1)
            skid.rotation_euler[2] = angle
            smat = bpy.data.materials.new(name=f"{skid.name}_Mat")
            smat.use_nodes = True
            smat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)
            smat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
            skid.data.materials.append(smat)
            return {"marker": skid.name, "type": "skid_mark", "length": length}

        if marker_type == "debris":
            import random
            count = params.get("count", 8)
            radius = params.get("radius", 3)
            for i in range(count):
                rx = location[0] + random.uniform(-radius, radius)
                ry = location[1] + random.uniform(-radius, radius)
                rz = location[2] + random.uniform(0.02, 0.15)
                bpy.ops.mesh.primitive_cube_add(size=random.uniform(0.05, 0.3), location=(rx, ry, rz))
                piece = bpy.context.active_object
                piece.name = f"Debris_{i}"
                piece.rotation_euler = (random.uniform(0, 6.28), random.uniform(0, 6.28), random.uniform(0, 6.28))
            return {"marker": "debris_field", "type": "debris", "pieces": count}

        return {"error": f"Unknown marker type: {marker_type}"}

    # ── ACTION: ghost_scenario ──
    if action == "ghost_scenario":
        source_name = params.get("source_vehicle")
        source = bpy.data.objects.get(source_name)
        if not source:
            return {"error": f"Source vehicle '{source_name}' not found"}
        ghost_name = params.get("name", f"{source_name}_Ghost")

        bpy.ops.object.select_all(action="DESELECT")
        source.select_set(True)
        for child in source.children_recursive:
            child.select_set(True)
        bpy.context.view_layer.objects.active = source
        bpy.ops.object.duplicate()
        ghost = bpy.context.active_object
        ghost.name = ghost_name

        ghost_mat = bpy.data.materials.new(name=f"{ghost_name}_GhostMat")
        ghost_mat.use_nodes = True
        gbsdf = ghost_mat.node_tree.nodes["Principled BSDF"]
        gbsdf.inputs["Base Color"].default_value = params.get("ghost_color", [0.3, 0.5, 1, 0.3])
        gbsdf.inputs["Alpha"].default_value = params.get("ghost_alpha", 0.3)

        for obj in [ghost] + list(ghost.children_recursive):
            if hasattr(obj.data, "materials"):
                obj.data.materials.clear()
                obj.data.materials.append(ghost_mat)

        if "location" in params:
            ghost.location = params["location"]
        if "rotation" in params:
            ghost.rotation_euler[2] = math.radians(params["rotation"])

        return {"ghost": ghost_name, "source": source_name, "alpha": params.get("ghost_alpha", 0.3)}

    # ── ACTION: set_time_of_day ──
    if action == "set_time_of_day":
        tod = params.get("time", "day").lower()

        # Always set Filmic view transform for professional look
        try:
            scene.view_settings.view_transform = "Filmic"
            scene.view_settings.look = "Medium High Contrast"
        except Exception:
            pass

        # Enable EEVEE improvements if applicable
        if scene.render.engine == _eevee_engine_id() and hasattr(scene, "eevee"):
            try:
                scene.eevee.use_gtao = True
                scene.eevee.use_ssr = True
            except Exception:
                pass

        # Use the existing lighting handler with optimized presets
        if tod == "day":
            result = handle_scene_lighting({"preset": "outdoor", "strength": params.get("strength", 1.0),
                                            "sun_energy": 5, "sun_elevation": 45})
        elif tod in ("dusk", "dawn"):
            result = handle_scene_lighting({"preset": "outdoor", "strength": params.get("strength", 0.7),
                                            "sun_energy": 2.5, "sun_elevation": 8})
            # Override sun color to warm orange
            for obj in bpy.data.objects:
                if obj.type == "LIGHT" and obj.data.type == "SUN":
                    obj.data.color = (1.0, 0.7, 0.4)
                    break
        elif tod == "night":
            result = handle_scene_lighting({"preset": "outdoor", "strength": params.get("strength", 0.15),
                                            "sun_energy": 0.3, "sun_elevation": -10})
            for obj in bpy.data.objects:
                if obj.type == "LIGHT" and obj.data.type == "SUN":
                    obj.data.color = (0.85, 0.9, 1.0)
                    obj.data.energy = 0.3
                    break
        elif tod == "overcast":
            result = handle_scene_lighting({"preset": "studio", "strength": params.get("strength", 0.8)})
        else:
            result = handle_scene_lighting({"preset": "outdoor", "strength": params.get("strength", 1.0)})

        result["time_of_day"] = tod
        result["filmic"] = True
        return result

    # ── ACTION: build_full_scene ──
    if action == "build_full_scene":
        results = {"elements": []}

        road_params = params.get("road", {"road_type": "intersection", "lanes": 2})
        road_params["action"] = "build_road"
        r = handle_forensic_scene(road_params)
        results["road"] = r
        results["elements"].extend(r.get("elements", []))

        for vp in params.get("vehicles", []):
            vp["action"] = "place_vehicle"
            r = handle_forensic_scene(vp)
            results["elements"].append(r.get("vehicle", ""))

        for fp in params.get("figures", []):
            fp["action"] = "place_figure"
            r = handle_forensic_scene(fp)
            results["elements"].append(r.get("figure", ""))

        for ap in params.get("annotations", []):
            ap["action"] = "add_annotation"
            ap["annotation_type"] = ap.pop("type", "label")
            handle_forensic_scene(ap)

        for mp in params.get("markers", []):
            mp["action"] = "add_impact_marker"
            mp["marker_type"] = mp.pop("type", "impact_point")
            handle_forensic_scene(mp)

        cam_type = params.get("cameras", "bird_eye")
        r = handle_forensic_scene({"action": "setup_cameras", "camera_type": cam_type})
        results["cameras"] = r.get("cameras", [])

        tod = params.get("time_of_day", "day")
        handle_forensic_scene({"action": "set_time_of_day", "time": tod})
        results["time_of_day"] = tod

        scene.render.resolution_x = params.get("resolution_x", 1920)
        scene.render.resolution_y = params.get("resolution_y", 1080)
        scene.render.engine = _eevee_engine_id()

        if params.get("frame_end"):
            scene.frame_start = 1
            scene.frame_end = params["frame_end"]

        results["total_elements"] = len(results["elements"])
        return results

    return {"error": f"Unknown forensic_scene action: {action}"}
