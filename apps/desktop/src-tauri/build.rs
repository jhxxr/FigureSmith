fn main() {
    let manifest = tauri_build::AppManifest::new().commands(&[
        "import_sam3_model",
        "import_rmbg_archive",
        "import_rmbg_folder",
        "open_models_directory",
    ]);
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(manifest))
        .expect("failed to configure Tauri ACL manifest");
}
