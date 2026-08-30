# Atemoya external revenue channels

This file records what the automated system can do without pretending that an
account, permission, or publisher exists when it does not.

## Current policy

| Channel | Collection | Publishing | Required one-time setup |
| --- | --- | --- | --- |
| GitHub Pages | Public sources and repository content | Supported by the reviewed Git branch and Pages deployment | Merge the reviewed feature branch |
| Blogger | Blogger API v3 | Supported after an Atemoya Google OAuth credential and blog ID are configured | Enable Blogger API, authorize the Atemoya account with the `blogger` scope, record the blog ID in n8n |
| Google Analytics 4 | Existing page events | Reporting is supported through the GA4 Data API after authorization | Enable the Data API, provide the numeric property ID, grant read access to the Atemoya credential |
| Naver Blog | Naver Search/DataLab may be used for research | No unattended official post-writing API is listed in the current Naver Open API catalog | Keep an approval-ready draft; publish manually or through an explicitly reviewed browser workflow |
| Naver Cafe | Naver Search API and Cafe API | Official Cafe post creation is available after Naver OAuth and cafe/menu authorization | Register a Naver application and approve the target cafe/menu |

Secrets, OAuth refresh tokens, API keys, passwords, cookies, and recovery codes
must remain in n8n credentials or the host secret store. They must never be
committed to this repository.

## Evidence and references

- Blogger post creation: <https://developers.google.com/blogger/docs/3.0/reference/posts/insert>
- GA4 reporting: <https://developers.google.com/analytics/devguides/reporting/data/v1/basics>
- Current Naver Open API catalog: <https://developers.naver.com/docs/common/openapiguide/apilist.md>
- Naver Blog app URL-scheme retirement notice: <https://developers.naver.com/notice/article/8595>

## Activation gate

External publishing must stay inactive until a test draft is created and its
returned URL is recorded. A successful login screen is not evidence of an API
connection. The acceptance test is:

1. create a draft through the channel API;
2. persist the returned post ID and URL;
3. collect a view/click report for that URL;
4. show the evidence in the Atemoya dashboard;
5. only then enable scheduled publishing.

This gate prevents the system from reporting "connected" merely because an
account page was opened in a browser.
