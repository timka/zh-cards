{
  description = "Chinese vocabulary tools and hashcards";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    hashcards = {
      url = "github:eudoxia0/hashcards";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    nixpkgs,
    hashcards,
    ...
  }: let
    systems = ["aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux"];
    forAllSystems = nixpkgs.lib.genAttrs systems;
    packagesFor = system: hashcards.packages.${system}.default;
  in {
    packages = forAllSystems (system: {
      default = packagesFor system;
      hashcards = packagesFor system;
    });

    devShells = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      default = pkgs.mkShell {
        packages = [(packagesFor system) pkgs.uv pkgs.zsh pkgs.glow];
      };
    });
  };
}
