# Restore drill (operator runbook)

Practice this on a **non-production** world first. Goal: prove a verified backup can replace the active world and that a failed restore rolls back.

## Prerequisites

- MineForge app healthy (`./deploy/mf smoke`)
- Bedrock profile running (`./deploy/mf up bedrock`) or a Fake/offline world under `/data/worlds`
- At least one signed-in admin
- Note current `level-name` on **Server → properties** (or Worlds → Active)

## Drill steps

1. **Baseline backup**  
   Open **Backups → Backup now**. Wait until the operation drawer shows success and the archive is **verified**.

2. **Optional: make a visible change**  
   Join the world and place a unique block / rename a chest, or create a marker file only if you know the world folder layout. Record what you will look for after restore.

3. **Take a second “current” backup** (optional safety) so you can return to post-drill state.

4. **Restore the baseline backup**  
   On **Backups**, choose the baseline row → **Restore**. Confirm. Watch the operation drawer through stop → extract → start → health-check.

5. **Verify**  
   - World is online  
   - Your marker from step 2 is **gone** (baseline restored)  
   - `level-name` still matches the intended world folder  

6. **Forced-failure awareness**  
   MineForge takes a **pre-restore** backup and swaps the world folder atomically. If startup health-check fails, it swaps back automatically and marks the operation rolled back. You should see a clear failure reason in the drawer — do not delete archives until you understand the outcome.

7. **Return to desired state**  
   Restore the “current” backup from step 3 if you need the post-drill world back.

## Pass criteria

- Restore completed (or clean rollback with reason)
- Server returns to a joinable state
- No orphaned temp directories left under `/data/worlds` (MineForge cleans up; spot-check if debugging)

## Notes

- Live backups use `save hold` / `save query` / `save resume` while players are online.
- Retention: `MINEFORGE_BACKUP_RETENTION_DAYS` (default 7); newest backup per world is kept.
