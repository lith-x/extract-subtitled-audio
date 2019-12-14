#! /usr/bin/env python

from argparse import ArgumentParser
from datetime import datetime, timedelta
from ffmpeg.nodes import Stream, OutputStream
from webvtt import WebVTT
import ffmpeg
import webvtt
import os

DEFAULT_PADDING = 100

# Number of seconds before "close enough" and stitch two subbed lines of dialogue together.
EPSILON = 0.01


def init_parser():
    parser = ArgumentParser()
    parser.add_argument("-i", "--input", metavar="filepath",
                        help="path to media file to use for audio", type=str, required=True)
    parser.add_argument("-s", "--subtitle", metavar="filepath",
                        help="path to .srt, .vtt, or .sbv file", type=str, required=True)
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
        subtitles[i].start = shift_time_string(subtitles[i].start, -padding)
        subtitles[i].end = shift_time_string(subtitles[i].end, padding)
        if subtitles[i+1].start_in_seconds - subtitles[i].end_in_seconds <= EPSILON:
            subtitles[i].end = subtitles[i+1].end
            del subtitles.captions[i+1]
        i -= 1
    return subtitles


def format_output_filename(filename: str, default: str) -> str:
    out = filename if filename else os.path.splitext(default)[0] + "_trimmed"
    return out if out.endswith(".mp3") else out + ".mp3"


def get_trimmed_ffmpeg_stream(input_filename: str, subtitle_filename: str, padding: int, output_filename: str) -> OutputStream:
    input_file = ffmpeg.input(input_filename)
    subtitles = get_reduced_subs(subtitle_filename, padding)

    trimmed_segments = [input_file.audio.filter("atrim",
                                                start=sub.start_in_seconds, end=sub.end_in_seconds) for sub in subtitles]
    concatenated_segments = ffmpeg.concat(*trimmed_segments, a=1, v=0)

    formatted_output_filename = format_output_filename(
        output_filename, input_filename)
    return ffmpeg.output(concatenated_segments, formatted_output_filename)


def run_as_command():
    args = init_parser()
    padding = args.padding or DEFAULT_PADDING
    stream = get_trimmed_ffmpeg_stream(
        args.input, args.subtitle, padding, args.output)
    stream.overwrite_output().run()


if __name__ == "__main__":
    run_as_command()
