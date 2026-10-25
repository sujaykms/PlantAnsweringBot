---
title: Plant Docs Assistant
emoji: 🏭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Ask plant safety, maintenance and quality docs; answers cite sources.
---

Answers floor supervisors' questions from safety procedures, maintenance manuals and quality standards.
Questions are routed to the right document set, answers are checked against the documents before they are shown,
and emergencies raise a banner that asks before notifying the plant operator.

Set the `OPENROUTER_API_KEY` secret in this Space's settings. Source: https://github.com/sujaykms/PlantAnsweringBot
