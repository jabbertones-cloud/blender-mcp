from server.reference_loop import attach, camera_solve, correct, get_state, reset, still_path
from server.motion_spec import compile_motion_spec


def setup_function():
    reset()


def test_attach_sets_implied_camera_for_still():
    state = attach({"role": "front", "path": "/tmp/ref.png", "tier": "review"})
    assert state["paths"]["front"] == "/tmp/ref.png"
    assert state["camera"] == "implied"
    assert still_path() == "/tmp/ref.png"


def test_correct_maps_delta_e_to_material():
    mapped = correct({"delta_e": 8.0, "delta_e_passed": False, "ssim_passed": True, "psnr_passed": True})
    assert mapped["next_key"] == "product.material"
    assert mapped["reason"] == "delta_e"


def test_correct_maps_ssim_to_camera():
    mapped = correct({"delta_e_passed": True, "ssim_passed": False, "psnr_passed": True})
    assert mapped["next_key"] == "product.camera"


def test_correct_maps_psnr_to_render_setup():
    mapped = correct({"ssim_passed": True, "psnr_passed": False})
    assert mapped["next_key"] == "product.render_setup"


def test_correct_maps_unsolved_camera():
    mapped = correct({"blocking_reason": "camera_unsolved"})
    assert mapped["next_key"] == "workflow.reference_camera_solve"


def test_camera_solve_still_unsupported():
    attach({"path": "/tmp/ref.png"})
    out = camera_solve({})
    assert out["status"] == "unsupported"
    assert out["blocking_reason"] == "still_camera_solve_unsupported"


def test_camera_solve_video_defers_to_workflow():
    attach({"role": "motion_plate", "path": "/tmp/plate.mp4"})
    out = camera_solve({})
    assert out["status"] == "deferred"
    assert out["blocking_reason"] == "use_workflow_reference_camera_solve"


def test_motion_spec_compiles_keyframes():
    ops = compile_motion_spec(
        {"keyframes": [{"frame": 1, "location": [0, 0, 0]}, {"frame": 24, "location": [1, 0, 0]}]},
        "Hero",
    )
    assert ops[0]["frame"] == 1
    assert ops[1]["location"] == [1, 0, 0]
    assert get_state()["tier"] == "review"
