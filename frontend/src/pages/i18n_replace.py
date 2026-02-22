# -*- coding: utf-8 -*-
import re

with open("f:/Github-WenShape/WenShape-main/frontend/src/pages/WritingSession.jsx", encoding="utf-8") as f:
    content = f.read()

# Step 1: Add useLocale import
ANCHOR = "import logger from '../utils/logger';"
NEW_IMPORT = ANCHOR + "
import { useLocale } from '../i18n';"
if "useLocale" not in content:
    content = content.replace(ANCHOR, NEW_IMPORT, 1)
    print("Added useLocale import")

# Step 2: Add const { t } = useLocale() to WritingSessionContent
HOOK_ANCHOR = "    const { state, dispatch } = useIDE();"
HOOK_NEW = HOOK_ANCHOR + "
    const { t } = useLocale();"
if "const { t } = useLocale()" not in content:
    content = content.replace(HOOK_ANCHOR, HOOK_NEW, 1)
    print("Added const { t } = useLocale()")

with open("f:/Github-WenShape/WenShape-main/frontend/src/pages/i18n_step1.txt", "w", encoding="utf-8") as f:
    f.write(content)
print("Written step1")