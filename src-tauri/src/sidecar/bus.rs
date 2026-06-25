use std::{
    io::{BufRead, BufReader, Write},
    process::{Child, ChildStderr, ChildStdin, ChildStdout, Command, Stdio},
    sync::mpsc,
    thread,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

use crate::core::Config;


pub fn spawn_daemon(config: &Config) -> Result<Child, String> {
    let mut cmd = if config.dev {
        let mut c = Command::new("uv");
        c.current_dir(&config.project_root);
        c.args(["run", "python", "py-sidecar/main.py"]);
        c
    } else {
        let exe = config.sidecar_bundle.join(super::DAEMON_EXE);

        if !exe.exists() {
            return Err(format!(
                "daemon binary not found: {}. Run 'pnpm build:daemon' first.",
                exe.display()
            ));
        }

        let mut c = Command::new(&exe);
        c.current_dir(&config.sidecar_bundle);
        c
    };

    cmd.stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    cmd.env("PYTHONIOENCODING", "utf-8");
    cmd.env("PYTHONUTF8", "1");

    if config.dev {
        let py_sidecar = config.project_root.join("py-sidecar");
        cmd.env("PYTHONPATH", py_sidecar);
    }

    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    cmd.spawn()
        .map_err(|e| format!("failed to spawn python daemon: {e}"))
}

#[derive(Clone)]
pub struct ToSidecar {
    writer_tx: mpsc::Sender<String>,
}

impl ToSidecar {
    pub fn start(mut stdin: ChildStdin) -> Self {
        let (writer_tx, writer_rx) = mpsc::channel::<String>();
        thread::spawn(move || {
            for msg in writer_rx {
                if stdin.write_all(msg.as_bytes()).is_err() {
                    break;
                }
                let _ = stdin.write_all(b"\n");
                let _ = stdin.flush();
            }
        });
        Self { writer_tx }
    }

    pub fn send(&self, message: String) {
        let _ = self.writer_tx.send(message);
    }
}

pub struct FromSidecar;
impl FromSidecar {
    pub fn start(stdout: ChildStdout, on_message: impl Fn(String) + Send + Sync + 'static) {
        thread::spawn(move || {
            let reader = BufReader::new(stdout);

            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        on_message(line.trim().to_string());
                    }
                    Err(_) => break,
                }
            }
        });
    }

    pub fn start_stderr(stderr: ChildStderr, on_error: impl Fn(String) + Send + Sync + 'static) {
        thread::spawn(move || {
            let reader = BufReader::new(stderr);

            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        on_error(line.trim().to_string());
                    }
                    Err(_) => break,
                }
            }
        });
    }
}