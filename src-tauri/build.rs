fn main() {
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR");
    let sidecar_dir = std::path::Path::new(&manifest_dir).join("resources/sidecar");
    println!("cargo:rerun-if-changed={}", sidecar_dir.display());

    if std::env::var("PROFILE").as_deref() == Ok("release") {
        let sidecar_name = if cfg!(target_os = "windows") {
            "tauri-py-daemon.exe"
        } else {
            "tauri-py-daemon"
        };
        let sidecar_path = sidecar_dir.join(sidecar_name);

        if !sidecar_path.is_file() {
            panic!(
                "Python sidecar binary not found at {}. Run 'pnpm build:daemon' before release build.",
                sidecar_path.display()
            );
        }
    }

    tauri_build::build()
}
