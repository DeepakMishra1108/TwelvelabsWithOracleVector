#!/bin/bash
# Quick Start Guide for Video Slicing Feature

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          VIDEO SLICING - QUICK START GUIDE                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if FFmpeg is installed
echo "🔍 Checking dependencies..."
if command -v ffmpeg &> /dev/null; then
    echo "   ✅ FFmpeg installed: $(ffmpeg -version | head -1)"
else
    echo "   ❌ FFmpeg not found"
    echo "   Install: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
    exit 1
fi

if command -v ffprobe &> /dev/null; then
    echo "   ✅ ffprobe installed"
else
    echo "   ❌ ffprobe not found (should come with FFmpeg)"
    exit 1
fi

echo ""
echo "📚 Available Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Test the slicing system"
echo "   $ python test_video_slicing.py"
echo "   Shows how different video durations would be chunked"
echo ""
echo "2. Check your video duration"
echo "   $ python test_video_slicing.py YOUR_VIDEO.mp4"
echo "   Displays duration and whether slicing is needed"
echo ""
echo "3. Slice a video"
echo "   $ python video_slicer.py YOUR_VIDEO.mp4"
echo "   Creates chunks in: YOUR_VIDEO_chunks/"
echo ""
echo "4. Slice with custom settings"
echo "   $ python video_slicer.py YOUR_VIDEO.mp4 ./output 110"
echo "   Args: <input> [output_dir] [max_chunk_minutes]"
echo ""
echo "5. View integration guide"
echo "   $ python INTEGRATION_GUIDE.py"
echo "   Shows how to integrate into Flask app"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📖 Documentation:"
echo "   • VIDEO_SLICING_SUMMARY.md - Complete overview"
echo "   • INTEGRATION_GUIDE.py - Flask integration steps"
echo "   • test_video_slicing.py --help - Test suite help"
echo ""
echo "🎯 For your Taylor Swift video (181 minutes):"
echo "   $ python video_slicer.py Taylor_Swift_Era_Tour_Compressed.mp4"
echo ""
echo "   Result: 2 chunks of ~90 minutes each"
echo "   ✓ Chunk 1: 0:00 → 1:30:31"
echo "   ✓ Chunk 2: 1:30:21 → 3:00:52"
echo "   ✓ Both under 120-minute limit"
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    READY TO USE! 🚀                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
