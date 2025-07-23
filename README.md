# Turtle AI

## Smart animal monitoring system using RTSP and FFmpeg to capture and analyze camera feeds

## Goal

To continuously capture video from cameras installed in a wildlife rehabilitation area to periodically analyze video clips to detect signs of animals in distress.

## Requirements

* Local run capability - cost, reliability, sustainability
* Runs Docker containers locally for Ollama (to run the open-source LLM), scheduler web service, and video capture web service
* Notifications via SMS/WhatsAppp 
* Address limitations with RTSP (Real-time Streaming Protocol) and FFmpeg (FF is fast-forward) 
* Deciding on the right open-source model to run locally (currently using Gemma3)
* Constant testing with model parameters and prompt engineering to get the right output for detections

## Reference Architecture

<img width="756" height="424" alt="smart-monitoring" src="https://github.com/user-attachments/assets/faee898b-6529-4da9-8298-46bf6f5da0f0" />
