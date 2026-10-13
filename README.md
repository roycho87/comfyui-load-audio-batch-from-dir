# ComfyUI Load Audio Batch From Dir

An audio version of **Load Image Batch From Dir (Inspire)** from [ComfyUI-Inspire-Pack](https://github.com/ltdrdata/ComfyUI-Inspire-Pack).
It reads the audio files in a folder, in the order you choose, and loads as many as you ask for.

## Install
Copy this folder into `ComfyUI/custom_nodes/` and restart ComfyUI. No extra packages are needed (it uses `torchaudio`, or `av` as a fallback, which ComfyUI already has).
The node appears as **Load Audio Batch From Dir** under `audio`.

## Inputs
| Input | Default | Meaning |
|---|---|---|
| `directory` | | Folder to read |
| `audio_load_cap` | 0 | Load at most this many files (0 = no limit) |
| `start_index` | 0 | Skip this many files first (-1 = the last file) |
| `load_always` | off | Re-run every time instead of only when the inputs or the folder change |
| `sort_method` | None | None, Alphabetical, Numerical (first number in the file name) or Datetime, ascending or descending |

## Outputs
* `audio` - the loaded files joined one after another into a single AUDIO (wav, mp3, flac, ogg, opus, m4a, aac, wma, aiff, mka)
* `count` - how many files were loaded

An image batch stacks frames, but audio files differ in length, so they are joined end to end instead. Files are converted to the first file's sample rate and channel count so they can be joined.

**One clip per run:** set `audio_load_cap` to 1 and drive `start_index` with a counter (for example a primitive set to *increment*) to step through a folder, one file per queued run.

## Differences from the Inspire node
* Audio files instead of images; no mask output.
* Folders that happen to match a file extension are skipped (the original crashes on them).
* The change check looks at the input values and the files' modified times, not only the input names.

## Status
The file selection and sorting were tested with a stub. The audio reading, resampling and joining have not been run on a real ComfyUI install yet. Please open an issue with the error text if a file fails to load.

## Credits
Adapted from `LoadImagesFromDirBatch` in [ComfyUI-Inspire-Pack](https://github.com/ltdrdata/ComfyUI-Inspire-Pack) by ltdrdata (GPL-3.0). Released under the same licence (GPL-3.0, see `LICENSE`).
