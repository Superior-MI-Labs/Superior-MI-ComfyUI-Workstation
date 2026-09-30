import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import character_library
import creation_helper

class CharacterLibraryTests(unittest.TestCase):
    def test_bundled_character_count_and_names(self):
        chars = character_library.scan_characters(include_bundled_fallback=True)
        names = {c.name for c in chars}
        self.assertGreaterEqual(len(chars), 21)
        self.assertIn("Kisha", names)
        self.assertIn("Vexa Emberpaw", names)
        self.assertIn("Juniper Hart", names)

    def test_filename_fallback_and_recursive_category(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sub = root / "Custom Team"
            sub.mkdir()
            (sub / "Alex River.png").write_bytes(b"not-an-image-but-scanner-only-needs-file")
            with mock.patch.object(character_library, "USER_ROOT", root), mock.patch.object(character_library, "BUNDLED_ROOT", root / "none"):
                chars = character_library.scan_characters()
            self.assertEqual(len(chars), 1)
            self.assertEqual(chars[0].name, "Alex River")
            self.assertEqual(chars[0].kind, "Custom Team")

    def test_sidecar_overrides_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); root.mkdir(exist_ok=True)
            img = root / "filename.png"; img.write_bytes(b"x")
            img.with_suffix('.json').write_text(json.dumps({"id":"stable-x","name":"Custom Name","kind":"Robot","tags":["custom","test"]}))
            with mock.patch.object(character_library, "USER_ROOT", root), mock.patch.object(character_library, "BUNDLED_ROOT", root / "none"):
                c = character_library.scan_characters()[0]
            self.assertEqual(c.uid, "stable-x")
            self.assertEqual(c.name, "Custom Name")
            self.assertEqual(c.kind, "Robot")
            self.assertIn("custom", c.tags)

    def test_user_character_wins_over_bundled_same_id(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); user=base/'user'; bundle=base/'bundle'
            for r in (user,bundle):
                (r/'Human').mkdir(parents=True)
                (r/'Human'/'Kisha.png').write_bytes(b'x')
                (r/'Human'/'Kisha.json').write_text(json.dumps({'id':'kisha','name':'Kisha'}))
            with mock.patch.object(character_library,'USER_ROOT',user), mock.patch.object(character_library,'BUNDLED_ROOT',bundle):
                chars=character_library.scan_characters()
            self.assertEqual(len(chars),1)
            self.assertEqual(chars[0].source_root,'user')

    def test_character_workflow_binds_reference(self):
        chars = character_library.scan_characters(include_bundled_fallback=True)
        kisha = next(c for c in chars if c.name == "Kisha")
        fake_models=set(creation_helper.MODES['Character Image (Qwen Image 2.1)']['required'])
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(character_library,'COMFY_INPUT',Path(td)), \
             mock.patch.object(creation_helper.preset_manager,'scan_model_files',return_value=fake_models):
            wf=creation_helper.build_workflow('Character Image (Qwen Image 2.1)','standing beside Lake Superior','Square','Fast',kisha)
            self.assertTrue(wf['10']['inputs']['image'].startswith('Superior-MI-Characters/'))
            self.assertIn('Kisha',wf['4']['inputs']['prompt'])
            self.assertIn('standing beside Lake Superior',wf['4']['inputs']['prompt'])


    def test_text_workflow_profiles_patch_dimensions(self):
        all_models=set()
        for spec in creation_helper.MODES.values(): all_models.update(spec['required'])
        with mock.patch.object(creation_helper.preset_manager,'scan_model_files',return_value=all_models):
            flux=creation_helper.build_workflow('Text Image (FLUX.2 Klein 4B)','test prompt','Phone Portrait','Quality')
            self.assertEqual(flux['6']['inputs']['width'],768)
            self.assertEqual(flux['6']['inputs']['height'],1344)
            self.assertEqual(flux['10']['inputs']['steps'],4)
            qwen=creation_helper.build_workflow('Text Image (Qwen Image 2.1)','test prompt','Landscape','Fast')
            self.assertEqual((qwen['5']['inputs']['width'],qwen['5']['inputs']['height']), (832,480))
            self.assertEqual(qwen['7']['inputs']['steps'],12)
            with tempfile.TemporaryDirectory() as td:
                td=Path(td)
                src=td/'source.png'; src.write_bytes(b'fake-image')
                comfy_input=td/'input'
                with mock.patch.object(character_library,'COMFY_INPUT',comfy_input):
                    wan=creation_helper.build_workflow('Video from Image (Wan2.2 TI2V 5B)','test motion','Phone Portrait','Normal',source_image=src)
            latent_id=next(k for k,v in wan.items() if v.get('class_type')=='Wan22ImageToVideoLatent')
            sampler_id=next(k for k,v in wan.items() if v.get('class_type')=='KSampler')
            load_id=next(k for k,v in wan.items() if v.get('class_type')=='LoadImage')
            self.assertEqual((wan[latent_id]['inputs']['width'],wan[latent_id]['inputs']['height'],wan[latent_id]['inputs']['length']), (576,1024,49))
            self.assertEqual(wan[sampler_id]['inputs']['steps'],16)
            self.assertTrue(wan[load_id]['inputs']['image'].startswith('Superior-MI-Video-Sources/'))

    def test_video_requires_source_image(self):
        all_models=set(creation_helper.MODES['Video from Image (Wan2.2 TI2V 5B)']['required'])
        with mock.patch.object(creation_helper.preset_manager,'scan_model_files',return_value=all_models):
            with self.assertRaises(ValueError) as cm:
                creation_helper.build_workflow('Video from Image (Wan2.2 TI2V 5B)','test motion','Phone Portrait','Normal')
        self.assertIn('Choose a source image',str(cm.exception))

    def test_missing_models_is_explicit(self):
        with mock.patch.object(creation_helper.preset_manager,'scan_model_files',return_value=set()):
            with self.assertRaises(RuntimeError) as cm:
                creation_helper.build_workflow('Text Image (FLUX.2 Klein 4B)','hello')
            self.assertIn('Required model files are missing', str(cm.exception))

if __name__ == '__main__':
    unittest.main()
