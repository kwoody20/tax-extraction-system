# Deployment Strategy

## Branch Structure

- **`main`**: Development branch for active development
- **`production`**: Stable branch for Railway deployment

## Workflow

### Daily Development
```bash
# Work on main branch
git checkout main
git add .
git commit -m "Your feature/fix"
git push origin main
# No Railway deployment triggered
```

### Deploy to Production
```bash
# When ready to deploy stable version
git checkout production
git merge main  # or git cherry-pick <commit-hash> for specific changes
git push origin production
# Railway automatically deploys
git checkout main  # Return to development
```

### Emergency Hotfix
```bash
# Create hotfix from production
git checkout production
git checkout -b hotfix/issue-name
# Make fixes
git add . && git commit -m "Fix: issue description"
git push origin hotfix/issue-name
# Create PR to production, merge
# Then backport to main
git checkout main
git cherry-pick <hotfix-commit>
git push origin main
```

## Railway Configuration

1. Service → Settings → Source
2. Branch: `production`
3. Auto-deploy: Enabled

## Best Practices

1. Test thoroughly on `main` before merging to `production`
2. Use semantic commit messages
3. Tag production releases: `git tag v1.0.0`
4. Keep production branch stable
5. Document breaking changes

## Rollback Strategy

If production deployment fails:
```bash
git checkout production
git revert HEAD  # or git reset --hard <last-good-commit>
git push origin production --force-with-lease
```

## Environment Variables

Managed in Railway dashboard:
- Different variables per environment if needed
- Secrets stay in Railway, not in code