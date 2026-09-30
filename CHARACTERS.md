# Character Library

The Workstation treats character identity as data, not hard-coded UI entries.

Persistent character root:

`~/Models/Media/Characters/`

Any supported image (`.png`, `.jpg`, `.jpeg`, `.webp`) anywhere below that folder becomes a selectable character. The image filename is the default character name. Subfolders become natural categories. For example:

```text
~/Models/Media/Characters/
├── My Characters/
│   ├── Alice.png
│   └── Bob.webp
└── Superior MI Characters/
    ├── Human/
    ├── Neko/
    └── Furry/
```

A same-name JSON sidecar is optional:

```text
Alice.png
Alice.json
```

Useful metadata fields are `id`, `name`, `collection`, `kind`, `role`, `identity`, `pronouns`, `body_type`, `species`, `description`, and `tags`.

The application recursively rescans the folder. It does not need code changes to add characters. Bundled starter characters are copied only when absent, so application upgrades do not overwrite user-edited character assets.

## Reference-sheet workflow

The bundled character assets are multi-view reference sheets. They are intended to anchor image generation and character identity. They are not ideal as a literal first video frame. The recommended path is:

1. Select a character.
2. Generate a clean single-scene still with Qwen Image 2.1.
3. Approve the still.
4. Animate the approved still with an image-to-video workflow such as Wan.

This avoids animating the text and multi-panel layout of a reference sheet.
