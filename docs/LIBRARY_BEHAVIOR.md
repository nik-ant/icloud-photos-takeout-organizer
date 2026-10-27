# Library behavior

## Sources and output

The organizer accepts iCloud Photos export folders and ZIP archives, including split exports and localized folder names. It reads media files and album CSV files, then copies supported photos and videos into a new destination. It does not modify the input files. CSV files, AppleDouble `._*` files, and other non-media files are not copied to the output.

Output media go into `Fotos/YYYY/` by capture year. The filename begins with a capture timestamp. Items without a usable embedded timestamp go into `Files Without Metadata/`, with a filename prefix based on filesystem modification time for easier inspection.

## Dates and metadata

The date precedence is:

1. Embedded media timestamp read by ExifTool.
2. A matching still image's timestamp for a Live Photo video.
3. Filesystem modification time as a fallback.

The fallback does not make a file eligible for a normal year folder. When ExifTool is installed, the organizer attempts to write date metadata to each copied file unless `--no-embed-metadata` is set. It can also correct an obvious image extension mismatch, such as JPEG content with a different suffix.

## Albums and Live Photos

Apple album CSV files determine album membership. Each album is recreated under `Albums/<album name>/` with its own media copies. Memories CSV files are included only with `--include-memories`. The same asset can therefore occupy space in its year folder and in multiple albums.

The script pairs Live Photo stills and videos by matching base names. A matched video uses the still's date and receives a `__live` filename suffix in the output. Check ambiguous or renamed pairs manually.

## Safe workflow

Run `--dry-run` first, use a new output folder, and compare the resulting file counts with the source export. Keep the source ZIP files or folders until the organized library has been checked. ZIP extraction uses temporary disk space; when you specify `--work-dir`, its extracted files remain for you to manage.
