from server.tripo_client import run_character_pipeline, set_transport


class _FakeTripo:
    def __init__(self):
        self.posts = []

    def post(self, path, body):
        self.posts.append((path, body))
        if path == "/generation/image-to-model":
            assert body["model"] == "P1-20260311"
            assert body["input"] == "https://example.com/p.png"
            return {"code": 0, "data": {"task_id": "t_model", "status": "success"}}
        if path == "/animations/rig-check":
            return {"code": 0, "data": {"status": "success", "riggable": True, "rig_type": "biped"}}
        if path == "/animations/rig":
            assert body["spec"] == "mixamo"
            return {"code": 0, "data": {"task_id": "t_rig", "status": "success"}}
        if path == "/animations/retarget":
            assert body["animations"] == ["preset:walk", "preset:idle", "preset:run"]
            return {
                "code": 0,
                "data": {
                    "status": "success",
                    "task_id": "t_anim",
                    "output": {"model_urls": ["https://cdn.tripo3d.ai/output/rigged.glb"]},
                },
            }
        raise AssertionError(path)

    def get(self, path):
        return {"code": 0, "data": {"status": "success", "task_id": "x"}}

    def download(self, url, dest):
        with open(dest, "wb") as handle:
            handle.write(b"glb")
        return dest


def test_character_pipeline_matches_tripo_v3_docs(tmp_path):
    fake = _FakeTripo()
    set_transport(fake)
    try:
        out = run_character_pipeline("https://example.com/p.png", dest_dir=str(tmp_path))
    finally:
        set_transport(None)
    assert out["filepath"].endswith(".glb")
    assert out["rig_type"] == "biped"
    assert [path for path, _ in fake.posts] == [
        "/generation/image-to-model",
        "/animations/rig-check",
        "/animations/rig",
        "/animations/retarget",
    ]
