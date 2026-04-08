# AiUE Quickstart

## Workspace Config

Start from:

- [pipeline_workspace.example.json](../examples/workspace/pipeline_workspace.example.json)

Use the stable top-level field:

- `version`

Point the workspace at:

- the Unreal host project
- the Blender addon repo
- the dataset and conversion roots
- this `AiUE` repo

## Probe

```powershell
.\aiue.ps1 probe `
  -WorkspaceConfig C:\path\to\pipeline_workspace.local.json `
  -Mode dual
```

## Run Capture Lab

```powershell
.\aiue.ps1 lab `
  -LabName capture `
  -WorkspaceConfig C:\path\to\pipeline_workspace.local.json `
  -SuiteName weapon_split
```

## Run Local Productization Gates

```powershell
.\run_alpha_triplines.ps1 `
  -WorkspaceConfig C:\path\to\pipeline_workspace.local.json
```
