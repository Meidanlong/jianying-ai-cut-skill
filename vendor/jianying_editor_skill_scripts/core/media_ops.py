import hashlib
import os
import shutil
import subprocess
import sys
from typing import Union

import pyJianYingDraft as draft
from pyJianYingDraft import trange
from pyJianYingDraft.exceptions import SegmentOverlap
from utils.formatters import get_duration_ffprobe_cached, safe_tim
from utils.media_normalizer import normalize_video_for_jianying, normalize_webm_for_jianying


class MediaOpsMixin:
    """
    JyProject 的媒体处理 Mixin。
    """

    def add_media_safe(
        self,
        media_path: str,
        start_time: Union[str, int] = None,
        duration: Union[str, int] = None,
        track_name: str = None,
        source_start: Union[str, int] = 0,
        **kwargs,
    ):
        if not os.path.exists(media_path):
            print(f"❌ Media Missing: {media_path}")
            return None

        ext = os.path.splitext(media_path)[1].lower()
        # Normalize WEBM to a stable MP4 profile before import to avoid parser incompatibilities.
        if ext == ".webm":
            normalized_path = normalize_webm_for_jianying(media_path)
            if not normalized_path:
                print(f"❌ WEBM normalization failed: {media_path}")
                return None
            media_path = normalized_path
            ext = ".mp4"
        elif ext in [".mp4", ".mov", ".m4v"]:
            normalized_path = normalize_video_for_jianying(media_path)
            if normalized_path:
                media_path = normalized_path
                ext = os.path.splitext(media_path)[1].lower()

        # 复制进草稿目录，使草稿自包含，规避 macOS 沙盒拦截及 Windows 5.9+ 外部素材丢失问题
        media_path = self._stage_local_asset(media_path)

        if ext in [".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"]:
            return self.add_audio_safe(media_path, start_time, duration, track_name or "AudioTrack")

        return self._add_video_safe(
            media_path, start_time, duration, track_name or "VideoTrack", source_start=source_start
        )

    def _stage_local_asset(self, media_path: str, subdir: str = "materials") -> str:
        """把外部本地素材复制进草稿目录内部（默认 materials/ 子目录），返回副本绝对路径。

        1. macOS (Darwin)：剪映为沙盒应用，草稿引用外部路径常因系统权限提示格式不支持或无法访问；
        2. 全平台 (Windows/macOS/Linux)：若素材在临时目录，源文件被清理会导致剪映 5.9+ 报“检测到媒体丢失”；
        复制进草稿目录可让工程自包含、路径永久稳定。
        若素材已在草稿目录内，则跳过复制。
        """
        try:
            draft_dir = getattr(self, "draft_dir", "")
            if not draft_dir:
                return media_path

            abs_media = os.path.abspath(media_path)
            abs_draft = os.path.abspath(draft_dir)

            try:
                if os.path.commonpath([abs_draft, abs_media]) == abs_draft:
                    return abs_media
            except ValueError:
                pass

            target_dir = os.path.join(abs_draft, subdir)
            os.makedirs(target_dir, exist_ok=True)

            ext = os.path.splitext(abs_media)[1].lower()
            digest = hashlib.md5(abs_media.encode("utf-8")).hexdigest()
            staged = os.path.join(target_dir, f"{digest}{ext}")

            if os.path.exists(staged) and os.path.getsize(staged) == os.path.getsize(abs_media):
                return staged

            shutil.copy2(abs_media, staged)
            return staged
        except Exception as e:
            print(f"⚠️ 素材复制进草稿目录失败，回退使用源路径: {e}")
            return media_path

    def _stage_media_for_jianying(self, media_path: str) -> str:
        """兼容 macOS 剪映沙盒的暂存接口（向后兼容/单测兼容）"""
        return self._stage_local_asset(media_path, subdir="media")

    def add_audio_safe(
        self,
        media_path: str,
        start_time: Union[str, int] = None,
        duration: Union[str, int] = None,
        track_name: str = "AudioTrack",
        source_start: Union[str, int] = 0,
        **kwargs,
    ):
        if start_time is None:
            start_time = self.get_track_duration(track_name)
        self._ensure_track(draft.TrackType.audio, track_name)

        # 容错：传入的可能是含视频轨的整片（.mov/.mp4）。
        # AudioMaterial 会拒绝含视频轨的文件（"音频素材不应包含视频轨道"），
        # 导致音频段被静默丢弃、出现音视频不同步。这里抽离出纯音频文件，
        # 保证音频与视频按同一 source_timerange 同步裁切。
        pure_audio = self._extract_pure_audio(media_path)
        if pure_audio:
            media_path = pure_audio

        # 与视频素材一致：把音频所在文件复制进草稿目录，保证自包含、路径稳定
        media_path = self._stage_local_asset(media_path)

        try:
            mat = draft.AudioMaterial(media_path)
            phys_duration = mat.duration
        except Exception:
            return None

        start_us = safe_tim(start_time)
        src_start_us = safe_tim(source_start)
        actual_duration = self._calculate_duration(duration, phys_duration - src_start_us)

        seg = draft.AudioSegment(
            mat,
            trange(start_us, actual_duration),
            source_timerange=trange(src_start_us, actual_duration),
        )
        target_track = self._find_available_audio_track_name(track_name, seg)
        self.script.add_segment(seg, target_track)
        return seg

    # 缓存：同一视频文件只抽离一次音频，避免每段重复解封装 498MB 大文件
    _pure_audio_cache: "dict[str, str]" = {}

    def _extract_pure_audio(self, media_path: str) -> str:
        """若文件含视频轨，则抽离其音频为独立 .m4a（AAC）文件并返回路径；否则返回 ""。

        目的：AudioMaterial 只能接受纯音频文件。当调用方传入的是整片视频
        （含视频轨）时，抽离出纯音频供音频轨使用，从而保证音视频同步裁切。
        结果按源文件绝对路径缓存。
        """
        src = os.path.abspath(media_path)
        if src in MediaOpsMixin._pure_audio_cache:
            return MediaOpsMixin._pure_audio_cache[src]

        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=index", "-of", "csv=p=0", src],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
            )
            has_video = bool(probe.stdout.strip())
        except Exception:
            has_video = False

        if not has_video:
            MediaOpsMixin._pure_audio_cache[src] = ""
            return ""

        parent = os.path.dirname(src)
        stem, _ = os.path.splitext(os.path.basename(src))
        out = os.path.join(parent, f".{stem}.__pure_audio__.m4a")
        try:
            if not (os.path.exists(out) and os.path.getsize(out) > 0):
                # 优先流拷贝：源已是 AAC 时，copy 能保留精确时长（避免重编码引入的
                # ~14ms 编码延迟导致音视频段错位）；非 AAC（如 apple_apac）再退回重编码。
                r = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", src, "-vn", "-c:a", "copy", out],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600,
                )
                if r.returncode != 0 or not (os.path.exists(out) and os.path.getsize(out) > 0):
                    subprocess.run(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                         "-i", src, "-vn", "-c:a", "aac", "-b:a", "192k", out],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600,
                    )
            if os.path.exists(out) and os.path.getsize(out) > 0:
                MediaOpsMixin._pure_audio_cache[src] = out
                return out
        except Exception as e:
            print(f"⚠️ 音频抽离失败（将跳过该段音频）: {e}")

        MediaOpsMixin._pure_audio_cache[src] = ""
        return ""

    def _add_video_safe(
        self,
        media_path: str,
        start_time: Union[str, int] = None,
        duration: Union[str, int] = None,
        track_name: str = "VideoTrack",
        source_start: Union[str, int] = 0,
        **kwargs,
    ):
        if start_time is None:
            start_time = self.get_track_duration(track_name)
        self._ensure_track(draft.TrackType.video, track_name)

        try:
            fallback_duration_us = safe_tim(duration) * 10 if duration else None
            mat = draft.VideoMaterial(media_path, duration=fallback_duration_us)
            phys_duration = mat.duration
        except Exception:
            return None

        if not phys_duration or phys_duration <= 0:
            ff_dur = get_duration_ffprobe_cached(media_path)
            if ff_dur > 0:
                phys_duration = int(ff_dur * 1000000)
                mat.duration = phys_duration

        if not self._explicit_res and not self._first_video_resolved:
            if hasattr(mat, "width") and mat.width > 0:
                self.script.width, self.script.height = mat.width, mat.height
            self._first_video_resolved = True

        start_us = safe_tim(start_time)
        src_start_us = safe_tim(source_start)
        actual_duration = self._calculate_duration(duration, phys_duration - src_start_us)

        seg = draft.VideoSegment(
            mat,
            trange(start_us, actual_duration),
            source_timerange=trange(src_start_us, actual_duration),
            volume=0,  # 视频轨静音：音频由独立的音频轨（与视频同步裁切）提供，避免双重音轨
        )
        self.script.add_segment(seg, track_name)
        return seg

    def add_cloud_media(
        self,
        query: str,
        start_time: Union[str, int] = None,
        duration: Union[str, int] = None,
        track_name: str = None,
    ):
        cm = self.cloud_manager
        local_path = cm.download_asset(query)
        if not local_path:
            return None

        asset_info = cm.find_asset(query)
        db_type = str(asset_info.get("type", "")).lower() if asset_info else ""
        source_db = str(asset_info.get("source_db", "")).lower() if asset_info else ""
        is_audio_db = source_db in {"cloud_music_library.csv", "cloud_sound_effects.csv"}
        is_audio_type = any(
            k in db_type for k in ["music", "audio", "sound", "bgm", "音效", "歌曲", "歌"]
        )
        is_audio = is_audio_db or is_audio_type

        if is_audio:
            default_track = (
                "BGM"
                if source_db == "cloud_music_library.csv"
                or any(k in db_type for k in ["music", "bgm", "歌曲", "歌"])
                else "AudioTrack"
            )
            return self.add_audio_safe(
                local_path, start_time, duration, track_name or default_track
            )
        return self.add_media_safe(local_path, start_time, duration, track_name or "VideoTrack")

    def add_cloud_music(
        self,
        query: str,
        start_time: Union[str, int] = None,
        duration: Union[str, int] = None,
        name: str = None,
        duration_s: float = None,
        track_name: str = "BGM",
    ):
        """
        通过 Cloud ID 添加云端音乐。直接注入 Material ID 补丁。
        """
        if start_time is None:
            start_time = self.get_track_duration(track_name)

        # 仅使用真实下载的本地缓存文件。虚拟路径（如 cloud_music_xxx.mp3）在磁盘上
        # 并不存在，会直接触发剪映“检测到媒体丢失”。下载失败时直接报错返回。
        local_path = self.cloud_manager.download_asset(query)
        if not local_path or not os.path.exists(local_path):
            print(f"❌ Cloud music download failed: '{query}'. Aborted to avoid media-missing error.")
            return None

        return self.add_audio_safe(
            local_path, start_time=start_time, duration=duration, track_name=track_name
        )

    def _find_available_audio_track_name(self, base_track_name: str, segment) -> str:
        preferred = base_track_name or "AudioTrack"
        if self._track_accepts_segment(preferred, segment):
            return preferred

        index = 1
        while True:
            candidate = f"{preferred}_{index}"
            self._ensure_track(draft.TrackType.audio, candidate)
            if self._track_accepts_segment(candidate, segment):
                return candidate
            index += 1

    def _track_accepts_segment(self, track_name: str, segment) -> bool:
        track = self.script.tracks.get(track_name)
        if track is None:
            return False
        try:
            for existing in track.segments:
                if existing.overlaps(segment):
                    return False
            return True
        except SegmentOverlap:
            return False

    def _ensure_track(self, track_type, track_name):
        """确保轨道存在，不存在则创建。"""
        if not track_name:
            return
        if track_name not in self.script.tracks:
            self.script.add_track(track_type, track_name)

    def _calculate_duration(self, req_dur, phys_dur_available):
        """计算实际应用时长，带容错。"""
        if req_dur:
            req_us = safe_tim(req_dur)
            return min(req_us, phys_dur_available) if phys_dur_available > 0 else req_us
        return phys_dur_available
