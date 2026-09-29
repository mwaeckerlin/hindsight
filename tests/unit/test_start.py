"""bin/start.py: keys from Docker secrets reach Hindsight, and nothing else."""
import importlib.util
import pathlib
import tempfile
import unittest

START = pathlib.Path(__file__).resolve().parents[2] / "bin" / "start.py"
spec = importlib.util.spec_from_file_location("start", START)
start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start)


class SecretsFromFiles(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def secret(self, name, content):
        path = pathlib.Path(self.directory.name) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_file_becomes_the_variable(self):
        path = self.secret("tenant", "the-tenant-key\n")
        result = start.secrets_from_files({"HINDSIGHT_API_TENANT_API_KEY_FILE": path})
        self.assertEqual(result, {"HINDSIGHT_API_TENANT_API_KEY": "the-tenant-key"})

    def test_every_hindsight_file_variable_is_read(self):
        tenant = self.secret("tenant", "t")
        llm = self.secret("llm", "l")
        result = start.secrets_from_files({
            "HINDSIGHT_API_TENANT_API_KEY_FILE": tenant,
            "HINDSIGHT_API_LLM_API_KEY_FILE": llm,
            "HINDSIGHT_API_PORT": "8888",
        })
        self.assertEqual(result, {
            "HINDSIGHT_API_TENANT_API_KEY": "t",
            "HINDSIGHT_API_LLM_API_KEY": "l",
            "HINDSIGHT_API_PORT": "8888",
        })

    def test_foreign_file_variables_stay_untouched(self):
        environment = {"OTHER_KEY_FILE": "/nowhere"}
        self.assertEqual(start.secrets_from_files(dict(environment)), environment)

    def test_both_sources_for_one_key_stop_the_start(self):
        path = self.secret("tenant", "file-key")
        with self.assertRaises(SystemExit) as stopped:
            start.secrets_from_files({"HINDSIGHT_API_TENANT_API_KEY_FILE": path,
                                      "HINDSIGHT_API_TENANT_API_KEY": "env-key"})
        self.assertIn("both set", str(stopped.exception))

    def test_missing_file_stops_the_start_and_names_it(self):
        with self.assertRaises(SystemExit) as stopped:
            start.secrets_from_files({"HINDSIGHT_API_LLM_API_KEY_FILE": "/run/secrets/absent"})
        self.assertIn("/run/secrets/absent", str(stopped.exception))

    def test_empty_file_stops_the_start(self):
        path = self.secret("empty", "\n")
        with self.assertRaises(SystemExit) as stopped:
            start.secrets_from_files({"HINDSIGHT_API_LLM_API_KEY_FILE": path})
        self.assertIn("empty", str(stopped.exception))

    def test_empty_file_variable_is_ignored(self):
        self.assertEqual(start.secrets_from_files({"HINDSIGHT_API_LLM_API_KEY_FILE": ""}), {})


class OptionalTenantKey(unittest.TestCase):
    def test_a_tenant_key_switches_the_key_check_on(self):
        result = start.tenant_key_check({"HINDSIGHT_API_TENANT_API_KEY": "k"})
        self.assertEqual(result["HINDSIGHT_API_TENANT_EXTENSION"], start.TENANT_EXTENSION)

    def test_without_a_tenant_key_the_service_runs_open(self):
        self.assertNotIn("HINDSIGHT_API_TENANT_EXTENSION", start.tenant_key_check({}))

    def test_an_extension_set_by_the_operator_stays(self):
        environment = {"HINDSIGHT_API_TENANT_API_KEY": "k", "HINDSIGHT_API_TENANT_EXTENSION": "own.module:Extension"}
        self.assertEqual(start.tenant_key_check(dict(environment)), environment)


if __name__ == "__main__":
    unittest.main()
