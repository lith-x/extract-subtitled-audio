#! /usr/bin/env python

from argparse import ArgumentParser
from datetime import datetime, timedelta
from webvtt import WebVTT
import ffmpeg
import webvtt
import os

DEFAULT_PADDING = 100


def init_parser():
    parser = ArgumentParser()
    parser.add_argument("-s", "--subtitle", metavar="filepath",
                        help="path to .srt, .vtt, or .sbv file", type=str, required=True)
    parser.add_argument("-i", "--input", metavar="filepath",
                        help="path to media file to use for audio", type=str, required=True)
    parser.add_argument("-o", "--output", metavar="filename",
                        help="name of the output file (default: [input]_trimmed.mp3)", type=str, required=False)
    parser.add_argument("-p", "--padding", metavar="ms",
                        help="time before and after subtitle to add (default: 100ms)", type=int, required=False)
    return parser.parse_args()


def shift_time_string(timestr: str, milliseconds: int) -> str:
    t = datetime.strptime(timestr, "%H:%M:%S.%f")
    delta = timedelta(milliseconds=milliseconds)
    t += delta
    newstr = t.strftime("%H:%M:%S.%f")
    newstr = newstr[0:len(newstr) - 3]
    return newstr


def get_subtitle_file(filename: str) -> WebVTT:
    file_ext = os.path.splitext(filename)[1]
    if file_ext == ".srt":
        return webvtt.from_srt(filename)
    elif file_ext == ".sbv":
        return webvtt.from_sbv(filename)
    elif file_ext == ".vtt":
        return webvtt.read(filename)
    else:
        raise ValueError(filename)


def get_reduced_subs(filename: str, padding: int) -> WebVTT:
    subtitles = get_subtitle_file(filename)
    i = len(subtitles) - 2
    while i >= 0:
        # TODO: handle when start/end go outside length of media
        subtitles[i].start = shift_time_string(subtitles[i].start, -padding)
        subtitles[i].end = shift_time_string(subtitles[i].end, padding)
        if subtitles[i+1].start_in_seconds - subtitles[i].end_in_seconds < 0:
            subtitles[i].end = subtitles[i+1].end
            del subtitles.captions[i+1]
        i -= 1
    return subtitles


def format_output_filename(filename: str, default: str) -> str:
    out = filename if filename else os.path.splitext(default)[0] + "_trimmed"
    return out if out.endswith(".mp3") else out + ".mp3"


def main():
    args = init_parser()
    padding = args.padding or DEFAULT_PADDING

    subs = get_reduced_subs(args.subtitle, padding)
    input_file = ffmpeg.input(args.input)

    trimmed_segments = [input_file.audio.filter("atrim",
                                                start=sub.start_in_seconds, end=sub.end_in_seconds) for sub in subs]
    trimmed_audio = ffmpeg.concat(*trimmed_segments, a=1, v=0)

    output_filename = format_output_filename(args.output, args.input)
    ffmpeg.output(trimmed_audio, output_filename).overwrite_output().run()


if __name__ == "__main__":
    main()
