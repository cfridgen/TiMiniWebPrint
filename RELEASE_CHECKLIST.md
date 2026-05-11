# Release Deployment Checklist

Use this checklist **only** when deploying a new Release version. Development versions skip this and go directly to Portainer.

## 1. Update Version References
- [ ] Update `APP_VERSION` in `Dockerfile` (if applicable)
- [ ] Update image tag in `docker-compose.release.yml` from current tag to new tag (e.g., `v1.0.0`)
- [ ] Update version in any other hardcoded locations

## 2. Create Git Tag
```bash
git tag -a v<VERSION> -m "Release v<VERSION>"
git push origin v<VERSION>
```

## 3. Verify GitHub Publish Workflow
- [ ] GitHub Actions workflow triggers automatically on tag push
- [ ] Workflow publishes image with both version tag and `release-latest` to ghcr.io
- [ ] Verify in GitHub Actions that workflow completed successfully

## 4. Deploy to Portainer Release Stack
- [ ] Run: `docker-compose -p timiniprint-release -f docker-compose.release.yml up -d` on homeserver
- [ ] Verify release endpoint: `curl http://192.168.1.20:8001/api/build-info`
- [ ] Test core functionality manually or via test suite

## 5. Communicate
- [ ] Tag GitHub release (optional, if using release notes)
- [ ] Update project documentation if needed

---

**Note:** Development builds go directly to Portainer without this checklist. Only use this when you explicitly request a Release deployment.
