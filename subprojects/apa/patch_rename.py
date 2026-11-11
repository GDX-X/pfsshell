"""Generate the APA driver with the local rename fix without changing ps2sdk."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()

before = r'''// Unofficial helper for renaming APA partitions.
static int apaRename(s32 device, const char *oldId, const char *newId)
{
    apa_cache_t *clink;
    int i, rv;

    // look to see if can make(newname) or not...
    if ((clink = apaFindPartition(device, newId, &rv)) != NULL) {
        apaCacheFree(clink);
        SignalSema(fioSema);
        return -EEXIST; // File exists
    }

    // look to see if open(oldname)
    for (i = 0; i < apaMaxOpen; i++) {
        if (hddFileSlots[i].f != NULL) {
            if (memcmp(hddFileSlots[i].id, oldId, APA_IDMAX) == 0) {
                SignalSema(fioSema);
                return -EBUSY;
            }
        }
    }

    // Do not allow system partitions (__*) to be renamed.
#ifndef APA_ALLOW_REMOVE_PARTITION_WITH_LEADING_UNDERSCORE
    if (oldId[0] == '_' && oldId[1] == '_')
        return -EACCES;
#endif

    // find :)
    if ((clink = apaFindPartition(device, oldId, &rv)) == NULL) {
        SignalSema(fioSema);
        return rv;
    }

    // do the renaming :) note: subs have no names!!
    memset(clink->header->id, 0, APA_IDMAX);
    strncpy(clink->header->id, newId, APA_IDMAX - 1);

    // touch creation time
    apaGetTime(&clink->header->created);
    clink->header->checksum = apaCheckSum(clink->header, 1);

    clink->flags |= APA_CACHE_FLAG_DIRTY;

    apaCacheFlushAllDirty(device);
    apaCacheFree(clink);

    return 0;
}
'''
after = r'''// Unofficial helper for renaming APA partitions.
static int apaRename(s32 device, const char *oldId, const char *newId)
{
    apa_cache_t *clink;
    int i, rv;

    // look to see if can make(newname) or not...
    if ((clink = apaFindPartition(device, newId, &rv)) != NULL) {
        apaCacheFree(clink);
        return -EEXIST; // File exists
    }

    // look to see if open(oldname)
    for (i = 0; i < apaMaxOpen; i++) {
        if (hddFileSlots[i].f != NULL) {
            if (memcmp(hddFileSlots[i].id, oldId, APA_IDMAX) == 0) {
                return -EBUSY;
            }
        }
    }

    // Do not allow system partitions (__*) to be renamed.
#ifndef APA_ALLOW_REMOVE_PARTITION_WITH_LEADING_UNDERSCORE
    if (oldId[0] == '_' && oldId[1] == '_')
        return -EACCES;
#endif

    // find :)
    if ((clink = apaFindPartition(device, oldId, &rv)) == NULL) {
        return rv;
    }

    // do the renaming :) note: subs have no names!!
    memcpy(clink->header->id, newId, APA_IDMAX);

    // touch creation time
    apaGetTime(&clink->header->created);
    clink->header->checksum = apaCheckSum(clink->header, 1);

    clink->flags |= APA_CACHE_FLAG_DIRTY;

    apaCacheFlushAllDirty(device);
    apaCacheFree(clink);

    return 0;
}
'''
if source.count(before) != 1:
    raise SystemExit("APA rename source changed; review the local patch before building")
source = source.replace(before, after, 1)

before = r'''int hddReName(iomanX_iop_file_t *f, const char *oldname, const char *newname)
{
    int rv;

    WaitSema(fioSema);
    rv = apaRename(f->unit, oldname, newname);
    SignalSema(fioSema);

    return rv;
}
'''
after = r'''int hddReName(iomanX_iop_file_t *f, const char *oldname, const char *newname)
{
    int rv;
    char oldId[APA_IDMAX + 1] = {0};
    char newId[APA_IDMAX + 1] = {0};
    size_t oldLength = strlen(oldname);
    size_t newLength = strlen(newname);

    /* APA identifiers are fixed-width fields, not ordinary C strings.
       apaFindPartition and the open-file check compare all APA_IDMAX bytes. */
    if (!oldLength || !newLength)
        return -EINVAL;
    if (oldLength > APA_IDMAX || newLength > APA_IDMAX)
        return -ENAMETOOLONG;
    memcpy(oldId, oldname, oldLength);
    memcpy(newId, newname, newLength);

    WaitSema(fioSema);
    rv = apaRename(f->unit, oldId, newId);
    SignalSema(fioSema);

    return rv;
}
'''
if source.count(before) != 1:
    raise SystemExit("APA rename source changed; review the local patch before building")
source = source.replace(before, after, 1)

Path(sys.argv[2]).write_text(source)
