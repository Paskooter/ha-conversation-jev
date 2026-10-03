# Upstream attribution

This repository is a fork of [luxus/ha-conversation-jev](https://github.com/luxus/ha-conversation-jev), starting at `07b6b8710a7387b8c8ff5fb061d0866bef19f7c1`. Upstream authored the classifier questions, routing gates, domain maps, exposure helpers and original tests. The original history is retained.

That upstream revision has no declared source license. This fork preserves its licensing status and does not assign a new license to the upstream code. HACS's **action-only** licence check for default catalogue inclusion is excluded in this custom-repository CI; the manifest and repository structure checks remain enabled. This release is installed through HACS **Custom repositories** and is not submitted as a default HACS integration.

Fork changes provide OpenRouter support, explicit provider selection and key validation, a selectable installed fallback agent, reliable local service results, real HA lifecycle tests, diagnostics, CI and owner setup documentation. Grok conversation and subscription authentication remain with the separately installed SpaceXAI integration.
