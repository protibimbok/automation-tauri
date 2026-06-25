#[macro_export]
macro_rules! error_log {
    ($($args:tt)*) => {
        eprintln!("{}", format_args!($($args)*))
    };
}