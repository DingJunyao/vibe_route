# Security Review: vibe_route

## Scope

Repository-wide source-backed scan of the Vue 3 frontend and FastAPI backend across authentication, authorization, files, exports, rendering, logging, and deployment configuration.

- Scan mode: repository
- Target kind: git_revision
- Target ID: target_sha256_30397640cfdfd8bb16e2b7f48080fab1f21d750873864d2ae4787625b3868889
- Revision: b53e45285cb9ecf82f10aef2ba824e24a86c8c1c
- Inventory strategy: repository
- Included paths: .
- Excluded paths: none
- Runtime or test status: Running services reported by the user; no runtime requests were sent.
- Artifacts reviewed: backend/app/core/config.py, backend/app/core/security.py, backend/app/core/deps.py, backend/app/api/auth.py, backend/app/api/admin.py, backend/app/api/tracks.py, backend/app/api/live_recordings.py, backend/app/api/logs.py, backend/app/api/interpolation.py, backend/app/api/overlay_templates.py, backend/app/api/poster.py, backend/app/api/shared.py, backend/app/services/interpolation_service.py, backend/app/services/overlay_template_service.py, backend/app/services/poster_service.py, backend/app/services/share_service.py, backend/app/services/track_service.py, backend/app/utils/playwright_export.py, frontend/src/components/map/GoogleMap.vue, frontend/src/components/map/TencentMap.vue, frontend/src/components/map/LeafletMap.vue, frontend/src/components/map/AMap.vue, frontend/src/components/map/BMap.vue, frontend/src/views/SharedTrack.vue, frontend/src/views/TrackDetail.vue, frontend/src/views/TrackMapOnly.vue, deploy/nginx/default.conf.template
- Scan context: HTTP and HTTPS must both remain supported; HTTPS is not required. Services were reported running, but the scan remained offline and did not use supplied credentials.

Limitations and exclusions:
- Repository inventory contains 406 files; remaining documentation, assets, migrations, and tests are deferred.
- Runtime reproduction of parser, concurrency, and deployment-specific behavior was not performed.
- Font traversal is directly validated for Windows path semantics and differs on Linux.
- Excluded frontend/node_modules/\*\*: Third-party dependencies are excluded by repository ignore rules.
- Excluded .git/\*\*: Version-control metadata is not application source.
- Excluded .venv/\*\* and .conda/\*\*: Local Python environments are not application source.
- Excluded frontend/node_modules/\*\*: Dependencies excluded by repository ignore rules.
- Excluded .git/\*\*: Version-control metadata excluded.

### Scan Summary

| Field | Value |
| --- | --- |
| Scan outcome | completed |
| Reportable findings | 13 |
| Severity mix | critical: 4, high: 6, medium: 3 |
| Confidence mix | high: 13 |
| Coverage | partial |
| Validation mode | source-backed static analysis with independent baseline, architecture, and focused reviews plus limited offline framework and path checks |

Canonical artifacts: `scan-manifest.json`, `findings.json`, and `coverage.json`. This report is a deterministic projection of those files.

## Threat Model

Vibe Route is a Vue 3/Vite SPA plus FastAPI/async-SQLAlchemy service for ingesting, storing, editing, visualizing, exporting, and sharing GPX/CSV/XLSX/KML/KMZ tracks. It uses bearer JWTs in localStorage, owner-scoped track APIs, public share and poster capability routes, live-recording upload tokens, generated media under /exports, and SQLite by default with optional MySQL/PostgreSQL. HTTP is supported and HTTPS is an external deployment option. \[frontend/src/stores/auth.ts:9-26; backend/app/main.py:371-391; backend/app/core/config.py:36-95\]

### Assets

- JWT bearer tokens in localStorage. \[frontend/src/stores/auth.ts:9-26\]
- User identities, password hashes, active/admin state, and invite codes. \[backend/app/models/user.py:12-29\]
- Track metadata and point histories including coordinates, timestamps, elevation, speed, and road or region fields. \[backend/app/models/track.py:15-115\]
- Share and live-recording capability tokens. \[backend/app/models/track.py:45-47; backend/app/models/live_recording.py:12-31\]
- Generated animation and overlay artifacts. \[backend/app/main.py:388-391\]

### Trust Boundaries

- Anonymous clients reach registration, login, public config, shared tracks, poster-secret reads, live-token reads, debug logs, and /exports. \[backend/app/api/auth.py:20-175; backend/app/api/shared.py:20-185; backend/app/main.py:388-391\]
- Authenticated users cross owner-scoped APIs; normal track and animation paths check ownership, while interpolation, overlay export, and poster generation do not. \[backend/app/services/track_service.py:159-176; backend/app/api/animation.py:31-40\]
- Admin authority is enforced by get_current_admin_user but depends on JWT integrity. \[backend/app/core/deps.py:114-134\]
- Backend storage covers the database, uploads, exports, and logs under host and container mount ACLs. \[Dockerfile:45-77; docker-compose.example.yml:28-30\]

### Attacker Capabilities

- Unauthenticated clients can reach public routes, submit logs, and attempt registration or login. \[backend/app/api/auth.py:20-175; backend/app/api/logs.py:53-108\]
- Authenticated non-owners can target integer IDs unless object authorization is checked. \[backend/app/services/track_service.py:159-176\]
- Share and live-recording token holders can access the scoped capabilities those tokens represent. \[backend/app/api/shared.py:20-185; backend/app/api/live_recordings.py:389-429\]

### Security Objectives

- JWT signing material must be deployment-specific and private. \[backend/app/core/config.py:31; backend/app/core/security.py:44\]
- Private tracks, interpolation records, templates, and generated media must remain owner-scoped. \[backend/app/services/track_service.py:159-176\]
- User-controlled metadata must be text-rendered or encoded before HTML insertion. \[frontend/src/components/map/GoogleMap.vue:183-227\]
- File serving and generated exports must remain inside an authorized root with scoped access. \[backend/app/main.py:388-391; backend/app/api/overlay_templates.py:242-284\]
- HTTP and HTTPS deployments must both remain supported. \[deploy/nginx/default.conf.template:7-10\]

### Assumptions

- HTTP and HTTPS must remain compatible and HTTPS is not forced. \[deploy/nginx/default.conf.template:7-10\]
- Windows and common Linux deployments differ in backslash path semantics.

## Findings

| Finding | Severity | Confidence | Detailed write-up |
| --- | --- | --- | --- |
| [Fixed JWT secret permits administrator token forgery](#finding-1) | critical | high | inline below |
| [Public font endpoint permits arbitrary file read on Windows](#finding-2) | critical | high | inline below |
| [Public font endpoint permits arbitrary file read on Windows](#finding-3) | critical | high | inline below |
| [Fixed JWT secret permits administrator token forgery](#finding-4) | critical | high | inline below |
| [Public poster secret exposes arbitrary private tracks](#finding-5) | high | high | inline below |
| [Interpolation APIs allow cross-user track reads and mutations](#finding-6) | high | high | inline below |
| [Stored XSS in shared-track map tooltips](#finding-7) | high | high | inline below |
| [Poster generation can render another user's track](#finding-8) | high | high | inline below |
| [Reflected XSS in live-recording placeholder response](#finding-9) | high | high | inline below |
| [Overlay export exposes arbitrary users' track data](#finding-10) | high | high | inline below |
| [Generated export artifacts are publicly reachable](#finding-11) | medium | high | inline below |
| [Unauthenticated log relay leaks live-recording tokens](#finding-12) | medium | high | inline below |
| [Private overlay templates are exposed by direct routes](#finding-13) | medium | high | inline below |

### Confidence Scale

| Label | Meaning |
| --- | --- |
| high | Direct evidence supports the finding with no material unresolved blocker. |
| medium | Evidence supports a plausible issue, but material runtime or reachability proof remains. |
| low | Evidence is incomplete and the item is retained only for explicit follow-up. |

<a id="finding-1"></a>

### [1] Fixed JWT secret permits administrator token forgery

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The signing path is direct and the workspace environment does not override the fixed default; user ID 1 is an active administrator. |
| Category | hard-coded cryptographic key |
| CWE | CWE-321, CWE-798 |
| Affected lines | backend/app/core/config.py:31, backend/app/core/security.py:44, backend/app/core/deps.py:58, backend/.env.example:11, backend/.env:7 |

#### Summary

The fixed default signing key permits an unauthenticated attacker to forge a valid administrator bearer token.

#### Root Cause

JWT integrity depends entirely on settings.SECRET_KEY; the repository supplies a fixed fallback, the workspace does not override it, and any correctly signed sub claim is trusted as the user identity.

#### Validation

Source and workspace state establish a practical administrator-token forgery path.

Validation method: source trace plus offline workspace verification

Assertions:
- Signing and verification both use settings.SECRET_KEY.
- The workspace environment does not override the fixed default.
- User ID 1 is an active administrator.

Counterevidence and remaining uncertainty:
- Documentation tells operators to change the key, but code does not enforce replacement.

Limitations:
- No live token was minted.

#### Dataflow

claims -\> jwt.encode with known key -\> jwt.decode -\> sub claim -\> active administrator

- **Source:** attacker-controlled token claims

- **Sink:** jwt.decode and admin dependency

- **Outcome:** The forged token is accepted as the referenced active user and admin dependency grants administrative access.

#### Reachability

Forge a token for an active administrator using the fixed default signing key.

- **Attacker:** unauthenticated network client

- **Entry point:** Bearer-token endpoints, especially /api/admin/\*

- **Outcome:** administrator impersonation

#### Severity

**Critical** — An unauthenticated attacker can forge an active administrator token and invoke the full admin API.

Rotating to an unknown high-entropy key eliminates the finding.

Impact assessment:
- **Level:** critical
- **Why:** Full administrator API access without credentials.

Likelihood assessment:
- **Level:** high
- **Why:** The signing key is a repository default and the workspace does not replace it.

#### Remediation

Require a high-entropy deployment-specific signing key, fail closed when it is missing or unchanged from the placeholder, rotate the key, and invalidate tokens issued under the weak key.

Tests:
- Startup fails for missing or placeholder SECRET_KEY.
- Tokens signed with the old default are rejected after rotation.

Preventive controls:
- Reject placeholder or low-entropy signing keys at startup.
- Use key identifiers and issuer/audience validation for rotation.

<a id="finding-2"></a>

### [2] Public font endpoint permits arbitrary file read on Windows

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The public route, unvalidated join, and file-read sink are direct source evidence; offline checks confirmed percent-decoded backslashes match the route and Windows path resolution escapes the font directory. |
| Category | path traversal |
| CWE | CWE-22 |
| Affected lines | backend/app/api/overlay_templates.py:242-247, backend/app/api/overlay_templates.py:258-275, backend/app/api/overlay_templates.py:329-332 |

#### Summary

The public font-file endpoint joins an unvalidated `font_id` to the font directory and can read arbitrary files on Windows.

#### Root Cause

The public font endpoint strips the `admin_` prefix but then uses the remaining client value as a filesystem path component. On Windows, encoded backslashes become separators, so `..` components escape the configured font directory before the file is read and returned.

**Public font route** — `backend/app/api/overlay_templates.py:242-247`

The route is public and does not require `get_current_user`; `font_id` is an unconstrained string path parameter.

```
@router.get("/fonts/{font_id}/file")
async def get_font_file(
    font_id: str,
    db: AsyncSession = Depends(get_db),
):
```

**Unvalidated path join** — `backend/app/api/overlay_templates.py:258-275`

The attacker-controlled remainder of `font_id` is joined directly to the font root without basename normalization or containment validation.

```
if font_id.startswith('admin_'):
    from app.core.config import settings

    filename = font_id[6:]
    admin_fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'

    for ext in ['.ttf', '.otf', '.ttc', '.woff2']:
        font_path = admin_fonts_dir / (filename + ext)
        if font_path.exists():
            return _serve_font_file(font_path)

    font_path = admin_fonts_dir / filename
    if font_path.exists():
        return _serve_font_file(font_path)
```

**File read sink** — `backend/app/api/overlay_templates.py:329-332`

The resolved path is opened directly and returned to the caller as the response body.

```
if content is None:
    print(f"DEBUG: Reading and converting source file: {source_path}")
    with open(source_path, 'rb') as f:
        content = f.read()
```

#### Validation

The source path is sufficient to establish the traversal. Offline checks confirmed the route captures encoded backslashes and Windows `Path` resolves them outside the font directory.

Validation method: source trace plus offline framework-aware path validation

**Public font route** — `backend/app/api/overlay_templates.py:242-247`

The route is public and does not require `get_current_user`; `font_id` is an unconstrained string path parameter.

```
@router.get("/fonts/{font_id}/file")
async def get_font_file(
    font_id: str,
    db: AsyncSession = Depends(get_db),
):
```

**Unvalidated path join** — `backend/app/api/overlay_templates.py:258-275`

The attacker-controlled remainder of `font_id` is joined directly to the font root without basename normalization or containment validation.

```
if font_id.startswith('admin_'):
    from app.core.config import settings

    filename = font_id[6:]
    admin_fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'

    for ext in ['.ttf', '.otf', '.ttc', '.woff2']:
        font_path = admin_fonts_dir / (filename + ext)
        if font_path.exists():
            return _serve_font_file(font_path)

    font_path = admin_fonts_dir / filename
    if font_path.exists():
        return _serve_font_file(font_path)
```

**File read sink** — `backend/app/api/overlay_templates.py:329-332`

The resolved path is opened directly and returned to the caller as the response body.

```
if content is None:
    print(f"DEBUG: Reading and converting source file: {source_path}")
    with open(source_path, 'rb') as f:
        content = f.read()
```

Assertions:
- The route has no authentication dependency.
- The remaining `font_id` is passed to `Path / filename` without normalization.
- The resolved path is read and returned without a containment check.

Counterevidence and remaining uncertainty:
- The direct exploit is specific to Windows path handling; Linux deployments require a different separator path and the current deployment uses Windows.

Limitations:
- No live request was sent to the running service; validation used source inspection plus an offline route-decoding and path-resolution check.

#### Dataflow

`font_id` -\> prefix stripping -\> Path join with unvalidated relative components -\> `font_path.exists()` -\> `_serve_font_file()` -\> `open(..., 'rb')`

- **Source:** attacker-controlled `font_id` path parameter

- **Sink:** open(source_path, 'rb')

- **Outcome:** The response contains the contents of an arbitrary readable file instead of a font.

**Public font route** — `backend/app/api/overlay_templates.py:242-247`

The route is public and does not require `get_current_user`; `font_id` is an unconstrained string path parameter.

```
@router.get("/fonts/{font_id}/file")
async def get_font_file(
    font_id: str,
    db: AsyncSession = Depends(get_db),
):
```

**Unvalidated path join** — `backend/app/api/overlay_templates.py:258-275`

The attacker-controlled remainder of `font_id` is joined directly to the font root without basename normalization or containment validation.

```
if font_id.startswith('admin_'):
    from app.core.config import settings

    filename = font_id[6:]
    admin_fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'

    for ext in ['.ttf', '.otf', '.ttc', '.woff2']:
        font_path = admin_fonts_dir / (filename + ext)
        if font_path.exists():
            return _serve_font_file(font_path)

    font_path = admin_fonts_dir / filename
    if font_path.exists():
        return _serve_font_file(font_path)
```

**File read sink** — `backend/app/api/overlay_templates.py:329-332`

The resolved path is opened directly and returned to the caller as the response body.

```
if content is None:
    print(f"DEBUG: Reading and converting source file: {source_path}")
    with open(source_path, 'rb') as f:
        content = f.read()
```

#### Reachability

An unauthenticated request can traverse out of the font directory on Windows and read arbitrary readable files, including deployment secrets.

- **Attacker:** unauthenticated network client

- **Entry point:** GET /api/overlay-templates/fonts/{font_id}/file

- **Outcome:** arbitrary readable-file disclosure

Limitations:
- The direct traversal is platform-dependent and was validated for the current Windows workspace; Linux deployments do not interpret backslashes as separators.

#### Severity

**Critical** — The endpoint is unauthenticated and its response can disclose `backend/.env` and other readable files on the current Windows deployment, giving direct access to cryptographic and database credentials.

A Linux-only deployment would lower exploitability of the backslash variant; direct path traversal under a supported separator would remain critical. Removing the client-controlled path fragment eliminates the finding.

Impact assessment:
- **Level:** critical
- **Why:** The server can read files such as `backend/.env`, exposing signing keys, database credentials, and other deployment secrets to an unauthenticated client.

Likelihood assessment:
- **Level:** high
- **Why:** Backslash-encoded path segments are captured by the route and interpreted as separators by Windows `Path`; the target files are ordinary readable workspace files.

#### Remediation

Normalize and resolve the font path, reject any path that is not contained under the font directory, and accept only server-generated font identifiers rather than client-supplied path fragments.

Tests:
- Assert `/api/overlay-templates/fonts/admin_..%5C..%5C.env/file` cannot read `backend/.env`.
- Assert a valid Windows font identifier still returns the font file.

Preventive controls:
- Centralize file serving behind a helper that resolves and verifies containment under an allowed root.
- Allowlist font identifiers and never accept filesystem paths or separators from the client.

<a id="finding-3"></a>

### [3] Public font endpoint permits arbitrary file read on Windows

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The public route, unvalidated join, and file read are direct source evidence; offline checks confirmed encoded backslashes match the route and Windows Path escapes the font directory. |
| Category | path traversal |
| CWE | CWE-22 |
| Affected lines | backend/app/api/overlay_templates.py:242, backend/app/api/overlay_templates.py:263, backend/app/api/overlay_templates.py:329 |

#### Summary

The public font endpoint can read arbitrary files on Windows through an unvalidated font_id path.

#### Root Cause

The public endpoint treats the remainder of font_id as a filesystem path. On Windows, encoded backslashes become separators, allowing parent components to escape the font root before the file is opened and returned.

#### Validation

Source and Windows path behavior establish an unauthenticated arbitrary file-read path.

Validation method: source trace plus offline path validation

Assertions:
- The route has no authentication dependency.
- Client input is joined without normalization.
- The resolved path is read without containment checks.

Counterevidence and remaining uncertainty:
- Linux does not treat backslash as a path separator.

Limitations:
- No live request was sent.

#### Dataflow

font_id -\> prefix stripping -\> unvalidated Path join -\> exists -\> file read

- **Source:** attacker-controlled font_id

- **Sink:** open(source_path, 'rb')

- **Outcome:** The response contains an arbitrary readable file instead of a font.

#### Reachability

Traverse out of the font directory on Windows using encoded backslashes and read an arbitrary readable file.

- **Attacker:** unauthenticated network client

- **Entry point:** GET /api/overlay-templates/fonts/{font_id}/file

- **Outcome:** arbitrary readable-file disclosure

#### Severity

**Critical** — Unauthenticated file read can expose backend/.env, cryptographic keys, and database credentials on the current Windows deployment.

A Linux-only deployment reduces this variant; any platform with client-controlled path fragments remains affected.

Impact assessment:
- **Level:** critical
- **Why:** backend/.env and other readable secrets can be disclosed.

Likelihood assessment:
- **Level:** high
- **Why:** Windows Path interprets encoded backslashes as separators.

#### Remediation

Resolve and verify that the font path remains under the configured root, reject separators and parent components, and use server-generated IDs for public font files.

Tests:
- Encoded backslash traversal cannot read backend/.env.
- A legitimate font identifier still returns the font.

Preventive controls:
- Centralize file serving behind a containment check.
- Accept only server-generated font identifiers, never path fragments.

<a id="finding-4"></a>

### [4] Fixed JWT secret permits administrator token forgery

| Field | Value |
| --- | --- |
| Severity | critical |
| Confidence | high |
| Confidence rationale | The signing and verification path is direct; the workspace configuration was checked offline and does not replace the fixed default, and user ID 1 is an active administrator. |
| Category | hard-coded cryptographic key |
| CWE | CWE-321, CWE-798 |
| Affected lines | backend/app/core/security.py:26-45, backend/app/core/deps.py:49-75, backend/app/core/deps.py:114-134, backend/app/core/config.py:31, backend/.env.example:11, backend/.env:7 |

#### Summary

The fixed default `SECRET_KEY` lets an unauthenticated attacker forge a valid bearer token for any active user, including an administrator.

#### Root Cause

The JWT integrity boundary depends entirely on `settings.SECRET_KEY`. The settings module provides a fixed fallback, the current workspace environment file does not override it, and the decoder accepts any correctly signed `sub` claim as the authenticated user.

**Token signing uses the settings secret** — `backend/app/core/security.py:26-45`

The application signs attacker-influenced claims with `settings.SECRET_KEY`; if that key is a fixed public default, signatures are forgeable.

```
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
```

**Token verification trusts the fixed key** — `backend/app/core/security.py:48-60`

Verification trusts any signature made with the same fixed key and does not bind the token to a server-side session or key version.

```
def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
```

**Subject claim is trusted as the user identity** — `backend/app/core/deps.py:49-75`

After signature validation, the server treats the `sub` claim as the authenticated user ID and loads that user.

```
token = parts[1]
payload = decode_access_token(token)

if payload is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

user_id: Optional[int] = payload.get("sub")
if user_id is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

try:
    user_id = int(user_id)
except (ValueError, TypeError):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

from app.services.user_service import user_service
user = await user_service.get_by_id(db, user_id)
```

#### Validation

The source trace and workspace configuration establish a practical token-forgery path; the only remaining prerequisite is the deployed key matching the repository default.

Validation method: source trace plus offline workspace verification

**Token signing uses the settings secret** — `backend/app/core/security.py:26-45`

The application signs attacker-influenced claims with `settings.SECRET_KEY`; if that key is a fixed public default, signatures are forgeable.

```
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
```

**Token verification trusts the fixed key** — `backend/app/core/security.py:48-60`

Verification trusts any signature made with the same fixed key and does not bind the token to a server-side session or key version.

```
def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
```

**Subject claim is trusted as the user identity** — `backend/app/core/deps.py:49-75`

After signature validation, the server treats the `sub` claim as the authenticated user ID and loads that user.

```
token = parts[1]
payload = decode_access_token(token)

if payload is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

user_id: Optional[int] = payload.get("sub")
if user_id is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

try:
    user_id = int(user_id)
except (ValueError, TypeError):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

from app.services.user_service import user_service
user = await user_service.get_by_id(db, user_id)
```

Assertions:
- Token creation and verification both use `settings.SECRET_KEY`.
- The current workspace environment file does not override the fixed default.
- An offline check confirmed user ID 1 is an active administrator.

Counterevidence and remaining uncertainty:
- Deployment documentation tells operators to change the key, but the code does not enforce replacement.

Limitations:
- No runtime token was minted during this scan.

#### Dataflow

attacker-crafted claims -\> `jwt.encode` with known key -\> `jwt.decode` -\> `payload.get('sub')` -\> active-user lookup -\> admin endpoints

- **Source:** attacker-controlled JWT claims

- **Sink:** jwt.encode and jwt.decode

- **Outcome:** A forged token is accepted as the referenced user and admin dependency grants administrative authority.

**Token signing uses the settings secret** — `backend/app/core/security.py:26-45`

The application signs attacker-influenced claims with `settings.SECRET_KEY`; if that key is a fixed public default, signatures are forgeable.

```
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
```

**Token verification trusts the fixed key** — `backend/app/core/security.py:48-60`

Verification trusts any signature made with the same fixed key and does not bind the token to a server-side session or key version.

```
def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
```

**Subject claim is trusted as the user identity** — `backend/app/core/deps.py:49-75`

After signature validation, the server treats the `sub` claim as the authenticated user ID and loads that user.

```
token = parts[1]
payload = decode_access_token(token)

if payload is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

user_id: Optional[int] = payload.get("sub")
if user_id is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

try:
    user_id = int(user_id)
except (ValueError, TypeError):
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")

from app.services.user_service import user_service
user = await user_service.get_by_id(db, user_id)
```

#### Reachability

An unauthenticated attacker can sign an HS256 token with the fixed repository default and set `sub` to an active administrator ID.

- **Attacker:** unauthenticated network client

- **Entry point:** any bearer-token endpoint, especially `/api/admin/*`

- **Outcome:** administrator impersonation

Limitations:
- No live token forgery was executed; validation is source-backed plus offline configuration and user-role checks.

#### Severity

**Critical** — The signing key is a repository default and the authenticated subject is trusted directly. Forging `sub` for an active administrator yields immediate full administrative compromise without credentials.

Raising confidence would require observing the same default in the active production process; rotating the key to unknown high entropy would eliminate the finding.

Impact assessment:
- **Level:** critical
- **Why:** The attacker can mint a token for an active administrator and invoke the full admin API surface without a password.

Likelihood assessment:
- **Level:** high
- **Why:** The signing material is a fixed repository default and the workspace configuration was verified not to override it.

#### Remediation

Require a high-entropy deployment-specific signing key, fail startup when it is absent or still a documented placeholder, rotate the current key, and invalidate all tokens issued under the weak key.

Tests:
- Assert startup fails when `SECRET_KEY` is missing or equal to the documented placeholder.
- Assert a token signed with the old default is rejected after rotation.

Preventive controls:
- Add startup validation that rejects missing, placeholder, or low-entropy signing keys.
- Use key identifiers and explicit issuer/audience validation to support rotation without trusting stale tokens.

<a id="finding-5"></a>

### [5] Public poster secret exposes arbitrary private tracks

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The shared default, missing ownership check, and sequential IDs are directly established. |
| Category | hard-coded credential and broken object authorization |
| CWE | CWE-798, CWE-639 |
| Affected lines | backend/app/core/config.py:95, backend/app/api/tracks.py:1012, backend/app/api/tracks.py:1094, frontend/src/views/TrackMapOnly.vue:81 |

#### Summary

The public default poster secret exposes arbitrary track metadata and full coordinate sets.

#### Root Cause

One shared poster value is both capability and authorization. Public endpoints skip ownership checks, and the frontend contains a fallback to the same public default.

#### Validation

Source and workspace state establish the default capability bypass.

Validation method: source trace plus offline workspace verification

Assertions:
- The secret is a fixed repository default.
- The workspace does not override it.
- The endpoints query by track ID alone and skip ownership checks.

Counterevidence and remaining uncertainty:
- A manually configured strong secret mitigates the default-value path.

Limitations:
- No live request was made.

#### Dataflow

known default -\> public endpoints -\> query by track_id -\> full track response

- **Source:** known poster secret plus sequential track_id

- **Sink:** public track and point response

- **Outcome:** The caller receives metadata and full coordinates for tracks it does not own.

#### Reachability

Use the public default poster secret to enumerate IDs and read complete track metadata and coordinates.

- **Attacker:** unauthenticated network client

- **Entry point:** GET /api/tracks/{track_id}/public and GET /api/tracks/{track_id}/points/public

- **Outcome:** private track disclosure

#### Severity

**High** — The endpoint discloses private location histories without authentication and is enumerable by sequential IDs.

A strong configured secret removes the default bypass; per-track authorization remains required.

Impact assessment:
- **Level:** high
- **Why:** Full location histories, timestamps, elevation, owner IDs, and filenames can be enumerated.

Likelihood assessment:
- **Level:** high
- **Why:** The secret has a public default and the endpoints lack ownership checks and rate limits.

#### Remediation

Remove the static poster secret, authorize reads against the user or a scoped per-track token, and rotate the current value.

Tests:
- A static default cannot read any track.
- A track-scoped token is rejected for another track or user.

Preventive controls:
- Use short-lived per-track signed capabilities.
- Never embed a shared capability secret in browser fallbacks.

<a id="finding-6"></a>

### [6] Interpolation APIs allow cross-user track reads and mutations

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | Every interpolation operation uses only the supplied resource ID and never resolves Track.user_id. |
| Category | broken object authorization |
| CWE | CWE-639, CWE-862 |
| Affected lines | backend/app/api/interpolation.py:25, backend/app/api/interpolation.py:63, backend/app/api/interpolation.py:94, backend/app/services/interpolation_service.py:54, backend/app/services/interpolation_service.py:350, backend/app/services/interpolation_service.py:492 |

#### Summary

Interpolation endpoints allow cross-user reads, coordinate previews, interpolation creation, and deletion.

#### Root Cause

The route layer authenticates callers but passes resource IDs to a service that queries TrackPoint and TrackInterpolation by ID only, with no Track.user_id predicate.

#### Validation

Source review establishes missing object authorization across the interpolation workflow.

Validation method: source trace

Assertions:
- Routes require authentication.
- Services query by track_id or interpolation_id only.
- Create and delete mutate persisted rows.

Counterevidence and remaining uncertainty:
- The caller must supply an existing numeric ID.

Limitations:
- No live cross-user request was executed.

#### Dataflow

authenticated request -\> route -\> service query by ID only -\> read/mutate/delete

- **Source:** attacker-controlled track_id or interpolation_id

- **Sink:** TrackInterpolation and TrackPoint mutations

- **Outcome:** The attacker reads, alters, or deletes another user's interpolation and point state.

#### Reachability

Supply another user's track or interpolation ID to read segments, preview coordinates, create interpolations, or delete records.

- **Attacker:** authenticated non-owner

- **Entry point:** GET/POST/DELETE /api/interpolation/\*

- **Outcome:** cross-user read and mutation

#### Severity

**High** — A normal authenticated user can disclose private location metadata and corrupt another user's track sequence.

Adding ownership predicates to all interpolation operations eliminates the finding.

Impact assessment:
- **Level:** high
- **Why:** Cross-user metadata disclosure and track integrity corruption are possible.

Likelihood assessment:
- **Level:** high
- **Why:** Integer resource IDs are enumerable and no ownership check exists.

#### Remediation

Require ownership of the target track before segment reads, previews, creation, or deletion and return 404 for non-owned resources.

Tests:
- A second user's track ID returns no interpolation data.
- A second user cannot create or delete interpolation state.

Preventive controls:
- Resolve every target track through a current-user-scoped helper.
- Apply one shared object-authorization policy to sibling interpolation routes.

<a id="finding-7"></a>

### [7] Stored XSS in shared-track map tooltips

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | Import, public response, field propagation, tooltip construction, and raw HTML sinks are all direct source paths with no sanitizer. |
| Category | stored cross-site scripting |
| CWE | CWE-79 |
| Affected lines | backend/app/api/shared.py:63, frontend/src/views/SharedTrack.vue:650, frontend/src/components/map/GoogleMap.vue:183, frontend/src/components/map/TencentMap.vue:1154, frontend/src/components/map/LeafletMap.vue:2301, frontend/src/components/map/AMap.vue:1021, frontend/src/components/map/BMap.vue:906 |

#### Summary

A malicious track owner can persist HTML in imported point fields and execute script when a victim views the shared-track map tooltip.

#### Root Cause

Imported point geography is stored and returned without encoding, then concatenated into HTML and written through innerHTML or vendor HTML APIs on a public page.

#### Validation

Source review establishes the persistent HTML-injection path.

Validation method: source trace

Assertions:
- Imported point fields are returned by the public shared API.
- They are copied without encoding.
- Tooltip construction writes raw values to innerHTML.

Counterevidence and remaining uncertainty:
- The victim must hover or tap a point.

Limitations:
- No live browser payload was executed.

#### Dataflow

CSV/XLSX import -\> TrackPoint fields -\> public shared response -\> tooltip HTML -\> innerHTML

- **Source:** attacker-controlled imported point fields

- **Sink:** innerHTML and HTML-accepting map APIs

- **Outcome:** The browser executes attacker-controlled HTML in the origin and can read the localStorage JWT.

#### Reachability

Store HTML in imported point fields, enable sharing, and trigger execution when a victim hovers the shared track.

- **Attacker:** authenticated track owner who enables sharing

- **Entry point:** Public /s/{token} page

- **Outcome:** same-origin script execution and token theft

#### Severity

**High** — The payload is persistent, publicly linkable, and executes in an origin that stores the bearer JWT.

A sanitizer or text-only rendering on every tooltip path removes the finding.

Impact assessment:
- **Level:** high
- **Why:** Same-origin script execution can steal the bearer token and act as the victim.

Likelihood assessment:
- **Level:** medium
- **Why:** The victim must open the public link and hover or tap a point.

#### Remediation

Encode or text-render all point-derived location fields before tooltip construction and remove raw innerHTML use for these values.

Tests:
- An HTML element in a shared point renders as text.
- The test passes for every map provider and hover path.

Preventive controls:
- Build tooltips with text nodes or a context-aware HTML encoder.
- Apply encoding to every map provider and asynchronous refresh path.

<a id="finding-8"></a>

### [8] Poster generation can render another user's track

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The route's current_user is unused for authorization and downstream public endpoints skip ownership checks. |
| Category | broken object authorization |
| CWE | CWE-639, CWE-862 |
| Affected lines | backend/app/api/poster.py:161, backend/app/services/poster_service.py:128, backend/app/api/tracks.py:1094 |

#### Summary

An authenticated user can make the server render another user's track as a poster because generation never checks track ownership.

#### Root Cause

The server-side poster route uses the caller-controlled track ID and the server secret to drive a public map page; authentication of the caller never authorizes the requested track.

#### Validation

Source review establishes cross-user track rendering.

Validation method: source trace

Assertions:
- The route requires a valid user but does not authorize track_id.
- The supplied track_id reaches the map-only URL.
- The public points endpoint skips ownership checks.

Counterevidence and remaining uncertainty:
- The server-held secret protects the internal flow but not the caller's right to the track.

Limitations:
- No live poster request was made.

#### Dataflow

request -\> poster route -\> server-held secret -\> map-only page -\> public points -\> screenshot

- **Source:** authenticated caller's track_id

- **Sink:** Playwright screenshot returned to the caller

- **Outcome:** The rendered poster can contain another user's actual track points.

#### Reachability

Send another user's track_id to the authenticated poster endpoint; the server supplies the capability secret and renders that track.

- **Attacker:** authenticated non-owner

- **Entry point:** POST /api/poster/generate

- **Outcome:** cross-user route disclosure

#### Severity

**High** — Authenticated users can obtain rendered private route data belonging to other accounts.

Adding an owner check before generation removes the finding.

Impact assessment:
- **Level:** high
- **Why:** The caller obtains a visual disclosure of another user's route.

Likelihood assessment:
- **Level:** high
- **Why:** Any authenticated account can supply sequential track IDs.

#### Remediation

Reject poster requests when the requested track is not owned by current_user and render using data fetched under the same ownership check.

Tests:
- A second user's track ID returns 403 or 404.
- The poster uses only the authenticated owner's data.

Preventive controls:
- Authorize every media generation request against the owning user.
- Fetch points server-side under that authorization.

<a id="finding-9"></a>

### [9] Reflected XSS in live-recording placeholder response

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The placeholder condition runs before lookup and the path token is interpolated without context-aware escaping. |
| Category | reflected cross-site scripting |
| CWE | CWE-79 |
| Affected lines | backend/app/api/live_recordings.py:544, backend/app/api/live_recordings.py:645, deploy/nginx/default.conf.template:29 |

#### Summary

The unauthenticated GPS Logger redirect reflects an unvalidated token into executable HTML.

#### Root Cause

The placeholder branch checks query values before resolving the recording token, then substitutes the raw path token into URL, script, and attribute contexts in a text/html response.

#### Validation

Source review establishes a direct reflected-XSS path without a valid token.

Validation method: source trace

Assertions:
- The placeholder branch precedes token resolution.
- The token is inserted into multiple executable contexts.
- The response is text/html.

Counterevidence and remaining uncertainty:
- The attack requires a victim to open a crafted link.

Limitations:
- No live browser payload was executed.

#### Dataflow

crafted token plus placeholder query -\> raw interpolation -\> text/html response

- **Source:** attacker-controlled token path segment

- **Sink:** text/html response

- **Outcome:** The crafted token executes JavaScript in the application origin.

#### Reachability

Send a crafted token and placeholder query value; the server reflects the token into executable HTML before validating it.

- **Attacker:** unauthenticated link sender

- **Entry point:** GET or POST /api/live-recordings/log/{token} with a placeholder query parameter

- **Outcome:** reflected XSS and token theft

#### Severity

**High** — An unauthenticated crafted link can execute JavaScript in the origin that stores the bearer JWT.

Moving token resolution before HTML construction or context-specific encoding removes the finding.

Impact assessment:
- **Level:** high
- **Why:** Same-origin script execution can steal the bearer JWT.

Likelihood assessment:
- **Level:** medium
- **Why:** A crafted link must be delivered to a victim, but the route is unauthenticated and /api is same-origin in deployed configurations.

#### Remediation

Remove raw token interpolation from the placeholder response, encode each output context separately, and carry the token only in a safely encoded redirect URL.

Tests:
- A token containing quotes or script delimiters cannot alter the response structure.
- An invalid token with a placeholder query does not execute script.

Preventive controls:
- Never interpolate user path values into inline JavaScript or HTML attributes.
- Resolve tokens before rendering and return a fixed error page when invalid.

<a id="finding-10"></a>

### [10] Overlay export exposes arbitrary users' track data

| Field | Value |
| --- | --- |
| Severity | high |
| Confidence | high |
| Confidence rationale | The route passes attacker IDs to a service with no owner predicate, and the renderer can output coordinates. |
| Category | broken object authorization |
| CWE | CWE-639, CWE-862 |
| Affected lines | backend/app/api/overlay_templates.py:478, backend/app/services/overlay_template_service.py:674, backend/app/services/overlay_template_service.py:700 |

#### Summary

Overlay export can request another user's track and private template by numeric ID.

#### Root Cause

The endpoint authenticates the caller but loads Track and OverlayTemplate by ID alone, then renders every point and returns the media.

#### Validation

Source review establishes a complete cross-user track rendering path.

Validation method: source trace

Assertions:
- The route requires authentication.
- The service selects track and template by ID only.
- All points are rendered and returned.

Counterevidence and remaining uncertainty:
- A system or public template is shareable but does not authorize another user's track.

Limitations:
- No live export was performed.

#### Dataflow

request -\> export route -\> load by ID -\> load all points -\> render

- **Source:** attacker-controlled track_id and template_id

- **Sink:** rendered overlay image sequence

- **Outcome:** The attacker receives rendered frames or a ZIP containing another user's track data.

#### Reachability

Supply another user's track and template IDs to render and receive their track data.

- **Attacker:** authenticated non-owner

- **Entry point:** POST /api/overlay-templates/tracks/{track_id}/export

- **Outcome:** cross-user track rendering and disclosure

#### Severity

**High** — The endpoint can reconstruct another user's private location history.

Adding track and template ownership checks removes the finding.

Impact assessment:
- **Level:** high
- **Why:** A custom template can render latitude, longitude, and other private point fields.

Likelihood assessment:
- **Level:** high
- **Why:** Track and template IDs are enumerable integer keys.

#### Remediation

Require the authenticated user to own the target track and permit template use only when owned, public, or system-defined.

Tests:
- A second user's track cannot export frames.
- A private template from another user cannot be used.

Preventive controls:
- Authorize track and template before loading rendering data.
- Apply a shared owner-or-public template policy.

<a id="finding-11"></a>

### [11] Generated export artifacts are publicly reachable

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The public mount and predictable filename construction are direct source evidence. |
| Category | sensitive file exposure |
| CWE | CWE-538, CWE-639 |
| Affected lines | backend/app/main.py:388, backend/app/utils/playwright_export.py:241, deploy/nginx/default.conf.template:45 |

#### Summary

Generated route media is exposed through an unauthenticated static directory with predictable filenames.

#### Root Cause

StaticFiles serves the complete export directory without authorization, while generated filenames combine sequential track IDs with second-resolution timestamps.

#### Validation

Source review establishes unauthenticated static access and predictable names.

Validation method: source trace

Assertions:
- The mount has no auth dependency.
- Filenames use track ID and timestamp.
- nginx proxies /exports without an authorization layer.

Counterevidence and remaining uncertainty:
- Directory listing is disabled.

Limitations:
- No timestamp brute force was performed.

#### Dataflow

track ID + timestamp -\> predictable filename -\> unauthenticated /exports URL

- **Source:** predictable track ID and timestamp filename

- **Sink:** StaticFiles response

- **Outcome:** A guessed or leaked URL returns another user's generated route media.

#### Reachability

Guess or obtain a track ID and timestamp, then request the generated export URL directly.

- **Attacker:** unauthenticated network client

- **Entry point:** GET /exports/...

- **Outcome:** generated artifact disclosure

#### Severity

**Medium** — The media contains private movement traces but requires a guessed or leaked filename.

A leaked URL or directory listing would raise likelihood; removing the public mount eliminates the finding.

Impact assessment:
- **Level:** medium
- **Why:** Generated media reveals precise movement traces.

Likelihood assessment:
- **Level:** medium
- **Why:** The filename is predictable but requires timestamp knowledge or brute force because directory listing is disabled.

#### Remediation

Remove the unauthenticated static mount, store exports outside public paths, and serve them through owner-authorized endpoints or signed URLs.

Tests:
- Unauthenticated access to a known export filename fails.
- Owner access succeeds and other users receive 403 or 404.

Preventive controls:
- Store generated artifacts outside the public root.
- Serve files through authenticated owner checks or short-lived signed URLs with high-entropy names.

<a id="finding-12"></a>

### [12] Unauthenticated log relay leaks live-recording tokens

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | Full token logging, unauthenticated POST broadcast, and unauthenticated WebSocket receive are direct source paths. |
| Category | sensitive credential exposure |
| CWE | CWE-200, CWE-522 |
| Affected lines | frontend/src/views/TrackDetail.vue:2858, backend/app/api/logs.py:53, backend/app/api/logs.py:81 |

#### Summary

The unauthenticated debug log relay can expose full live-recording tokens.

#### Root Cause

The frontend logs the full live-recording WebSocket URL while the backend log relay accepts and broadcasts messages without authentication, exposing the token to any listener.

#### Validation

Source review establishes the token-to-log-to-listener path.

Validation method: source trace

Assertions:
- TrackDetail logs the full token-bearing URL.
- The log POST route has no authentication.
- The log WebSocket has no authentication or environment gate.

Counterevidence and remaining uncertainty:
- The leak requires remote logging and an active recording.

Limitations:
- No live WebSocket capture was performed.

#### Dataflow

remote logging -\> full token log -\> POST /api/logs -\> unauthenticated WS broadcast -\> token capture

- **Source:** full token in a frontend console log

- **Sink:** unauthorized live-recording upload

- **Outcome:** A listener captures an active live-recording token and can inject track points.

#### Reachability

Listen to the unauthenticated log relay while a live-recording page logs its full token-bearing URL.

- **Attacker:** unauthenticated network listener

- **Entry point:** POST /api/logs and WebSocket /api/ws/logs

- **Outcome:** live-token theft and data injection

#### Severity

**Medium** — Token theft enables unauthorized injection into an active recording but requires remote logging and an active session.

Token redaction or authenticated log transport removes the finding.

Impact assessment:
- **Level:** medium
- **Why:** Captured active tokens permit unauthenticated point injection.

Likelihood assessment:
- **Level:** medium
- **Why:** Remote logging must be enabled and a live recording must be active, but the listener is unauthenticated.

#### Remediation

Redact capability tokens and require authenticated access to log ingestion and viewing; disable the relay outside explicit development use.

Tests:
- Token-bearing URLs never appear in logs.
- Unauthenticated clients cannot post or read debug logs.

Preventive controls:
- Never log capability tokens or token-bearing URLs.
- Authenticate and environment-gate log ingestion and viewing.

<a id="finding-13"></a>

### [13] Private overlay templates are exposed by direct routes

| Field | Value |
| --- | --- |
| Severity | medium |
| Confidence | high |
| Confidence rationale | The direct lookup is visibility-blind and the list path proves the intended owner/public/system policy. |
| Category | broken object authorization |
| CWE | CWE-639, CWE-862 |
| Affected lines | backend/app/api/overlay_templates.py:57, backend/app/api/overlay_templates.py:108, backend/app/api/overlay_templates.py:123, backend/app/api/overlay_templates.py:164, backend/app/services/overlay_template_service.py:53, backend/app/services/overlay_template_service.py:77, backend/app/services/overlay_template_service.py:145 |

#### Summary

Authenticated users can read, preview, export, or clone another user's private overlay templates by ID.

#### Root Cause

The common template lookup filters only by ID. Direct detail, export, preview, and clone operations reuse it, bypassing the list query's owner-or-public-or-system policy.

#### Validation

Source review establishes a complete bypass of the intended template visibility policy.

Validation method: source trace

Assertions:
- Detail, export, and preview use the ID-only lookup.
- Duplicate copies any source config into the caller's account.

Counterevidence and remaining uncertainty:
- System and public templates are intentionally shared; private non-owner templates are not.

Limitations:
- No live template request was made.

#### Dataflow

template_id -\> ID-only lookup -\> response/export/duplicate

- **Source:** attacker-controlled template_id

- **Sink:** template response, YAML export, or cloned record

- **Outcome:** The attacker can read, export, preview, or persistently clone another user's private template.

#### Reachability

Enumerate template IDs and call detail, preview, export, or duplicate routes to access private templates.

- **Attacker:** authenticated non-owner

- **Entry point:** GET/duplicate/export/preview /api/overlay-templates/{template_id}\*

- **Outcome:** private template disclosure

#### Severity

**Medium** — Private design configuration is exposed and can be persistently copied, though it is less sensitive than track data.

Applying the list visibility policy to all direct template routes removes the finding.

Impact assessment:
- **Level:** medium
- **Why:** Private template configuration and reusable design data are disclosed.

Likelihood assessment:
- **Level:** high
- **Why:** Template IDs are sequential and direct routes require only authentication.

#### Remediation

Apply owner-or-public/system visibility checks before returning, rendering, exporting, or cloning any overlay template.

Tests:
- A non-owner receives 404 or 403 for a private template.
- Public and system templates remain cloneable.

Preventive controls:
- Use one policy-aware lookup for every template read, export, preview, and clone.
- Keep private templates accessible only through the owner-scoped list query.

## Reviewed Surfaces

| Surface | Risk Area | Outcome | Notes |
| --- | --- | --- | --- |
| JWT issuance and verification | Authentication | Reported | Fixed signing default and direct subject trust permit administrator token forgery. |
| Public font file serving | Path traversal | Reported | Unauthenticated Windows path traversal reaches arbitrary readable files. |
| Poster capability and public track reads | Credentials and authorization | Reported | Default capability gates arbitrary track metadata and coordinate reads. |
| Shared-track map tooltips | Cross-site scripting | Reported | Imported point fields reach innerHTML and vendor HTML APIs without encoding. |
| Live-recording placeholder response | Cross-site scripting | Reported | Unvalidated path token is reflected into executable HTML before lookup. |
| Interpolation ownership | Broken object authorization | Reported | Track and interpolation IDs are not bound to the caller. |
| Overlay export ownership | Broken object authorization | Reported | Track and template IDs are loaded without owner predicates before rendering. |
| Poster generation ownership | Broken object authorization | Reported | Authenticated track_id is rendered with the server-held secret without ownership checks. |
| Private overlay template visibility | Broken object authorization | Reported | Direct detail, preview, export, and duplicate routes bypass the list visibility policy. |
| Debug log relay | Sensitive data exposure | Reported | Public POST/WS endpoints can relay full live-recording tokens from frontend logs. |
| Generated export storage | Sensitive file exposure | Reported | Static /exports is unauthenticated and filenames use predictable ID and timestamp components. |
| User font upload path handling | not recorded | Rejected | The path write lacks basename normalization, but the current API omits the required is_admin argument and fails before writing. |
| Share token generation | not recorded | Rejected | random.choices is not preferred, but practical prediction or brute force was not established; use secrets for hardening. |
| Public map-layer configuration | not recorded | No issue found | Map keys are intended for browser SDKs; provider-side restrictions are external. Geocoding config is not public. |
| SQL construction | not recorded | No issue found | Spatial queries use bound parameters; dynamic table names come from a fixed internal level map. |
| Invite-code consumption | not recorded | Needs follow-up | Separate validate and consume transactions may permit a max_uses race. |
| KML and XML parsing | not recorded | Needs follow-up | Default lxml parser options should be hardened and tested. |
| Administrative archive imports | not recorded | Needs follow-up | Uncompressed-size and file-count budgets are absent; traversal behavior is dependency-specific. |

## Open Questions And Follow Up

- Which deployment platform serves the public font endpoint? Windows path semantics make the traversal directly reachable; Linux behavior differs.
- Are provider-side origin, IP, quota, and scope restrictions configured for map and geocoding keys?
- Does the selected database serialize concurrent invite-code consumption strongly enough to prevent a max_uses bypass?
- Do deployed lxml/gpxpy versions enforce entity-expansion and external-entity limits consistently?
- KML uses lxml default parser options; safe flags and entity/resource limits need runtime validation.
  - Follow-up prompt: Review deferred unit deferred-kml-parser and close its stated proof gap. Paths: backend/app/services/track_service.py.
- Admin ZIP/RAR imports lack uncompressed-size and file-count budgets; dependency-specific traversal behavior was not fully established.
  - Follow-up prompt: Review deferred unit deferred-archive-budgets and close its stated proof gap. Paths: backend/app/utils/archive_helper.py, backend/app/api/admin.py.
- Invite-code validation and consumption are separate transactions; concurrency behavior requires database-specific reproduction.
  - Follow-up prompt: Review deferred unit deferred-invite-race and close its stated proof gap. Paths: backend/app/services/config_service.py, backend/app/api/auth.py.
- The inventory contains 406 files; this pass fully covered the runtime authentication, authorization, storage, file, logging, and rendering paths but not every documentation, asset, migration, and test file.
  - Follow-up prompt: Review deferred unit deferred-full-inventory and close its stated proof gap. Paths: backend/alembic/\*\*, backend/tests/\*\*, frontend/src/views/\*\*, docs/\*\*.
