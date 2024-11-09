{
  self,
  inputs,
  system,
  fetchFromGitHub,
}:

let
  lib = self.lib.${system};
in lib.mkFont {
  name = "open-gorton";
  src = fetchFromGitHub {
    owner = "dakotafelder";
    repo = "open-gorton";
    rev = "30094223a4f1e54e44ec3e2c39477f1b7e1006e4";
    hash = "sha256-5+XP9Q+KvNqFwtUAZAIjhfodUCJ2fyWCkwE6M0ILxgY=";
  };
}
