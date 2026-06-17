import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

import org.apache.fontbox.ttf.NameRecord;
import org.apache.fontbox.ttf.NamingTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for the TrueType {@code name} table accessors.
 *
 * Loads a font program directly via FontBox ({@link TTFParser}) and emits two
 * canonical sections covering the surfaces a non-symbolic PDF font subset
 * walks:
 *
 *   - One {@code RECORD} line per {@link NameRecord} in read order — the
 *     {@code (nid, plat, enc, lang)} tuple plus the decoded string.
 *     Verifies the UTF-16BE / Mac-Roman decode and the priority lookup
 *     map is keyed on the canonical platform / encoding / language ids.
 *   - For each canonical (platform, encoding, language) tuple PDFBox itself
 *     queries (Windows-Unicode-BMP-en-US, Mac-Roman-English, Unicode-platform
 *     -en) a {@code LOOKUP} line per name id {@code 0..8}. Verifies the
 *     UTF-16BE / Mac-Roman decode landed in the right priority-map slot.
 *   - The three named accessors PDFBox itself exposes via
 *     {@link NamingTable#getFontFamily()}, {@link NamingTable#getFontSubFamily()}
 *     and {@link NamingTable#getPostScriptName()} (the priority-resolved
 *     family / sub-family / PostScript name — NID 6 is the high-value case
 *     because {@code PDFontDescriptor.getFontName} reads it).
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> NameTableProbe <font.ttf>
 *
 * Output: UTF-8, tab-delimited, deterministic line order. Records are sorted
 * by (nid, plat, enc, lang) so the line order is independent of the font's
 * on-disk record order (both PDFBox and pypdfbox preserve read order, but the
 * point is to compare the lookup map content rather than the on-disk layout).
 * Canonical lines:
 *   COUNT    \t <numberOfRecords>
 *   RECORD   \t <nid> \t <plat> \t <enc> \t <lang> \t <string|NULL>
 *   LOOKUP   \t <nid> \t <plat> \t <enc> \t <lang> \t <string|NULL>
 *   FAMILY   \t <string|NULL>
 *   SUBFAMILY\t <string|NULL>
 *   PSNAME   \t <string|NULL>
 */
public final class NameTableProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String path = args[0];

        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(new File(path)));
            NamingTable naming = ttf.getNaming();
            List<NameRecord> records = (naming == null)
                ? new ArrayList<>()
                : new ArrayList<>(naming.getNameRecords());

            // Sort records by (nid, plat, enc, lang) so the canonical line
            // order is independent of the font's on-disk record order.
            records.sort(new Comparator<NameRecord>() {
                @Override
                public int compare(NameRecord a, NameRecord b) {
                    int c = Integer.compare(a.getNameId(), b.getNameId());
                    if (c != 0) return c;
                    c = Integer.compare(a.getPlatformId(), b.getPlatformId());
                    if (c != 0) return c;
                    c = Integer.compare(a.getPlatformEncodingId(), b.getPlatformEncodingId());
                    if (c != 0) return c;
                    return Integer.compare(a.getLanguageId(), b.getLanguageId());
                }
            });

            out.printf("COUNT\t%d%n", records.size());
            for (NameRecord r : records) {
                String s = r.getString();
                out.printf(
                    "RECORD\t%d\t%d\t%d\t%d\t%s%n",
                    r.getNameId(),
                    r.getPlatformId(),
                    r.getPlatformEncodingId(),
                    r.getLanguageId(),
                    s == null ? "NULL" : escape(s)
                );
            }
            // (platform, encoding, language) tuples PDFBox itself queries via
            // its 4-arg getName overload. Covers the Windows-Unicode-BMP en-US
            // path (UTF-16BE decode), the Mac-Roman English path (mac_roman
            // decode), and the Unicode-platform path (UTF-16BE under platform 0).
            int[][] tuples = new int[][] {
                {NameRecord.PLATFORM_WINDOWS, NameRecord.ENCODING_WINDOWS_UNICODE_BMP, NameRecord.LANGUAGE_WINDOWS_EN_US},
                {NameRecord.PLATFORM_MACINTOSH, NameRecord.ENCODING_MACINTOSH_ROMAN, NameRecord.LANGUAGE_MACINTOSH_ENGLISH},
                {NameRecord.PLATFORM_UNICODE, NameRecord.ENCODING_UNICODE_2_0_BMP, NameRecord.LANGUAGE_UNICODE},
            };
            for (int nid = 0; nid <= 8; nid++) {
                for (int[] t : tuples) {
                    String s = (naming == null) ? null : naming.getName(nid, t[0], t[1], t[2]);
                    out.printf(
                        "LOOKUP\t%d\t%d\t%d\t%d\t%s%n",
                        nid, t[0], t[1], t[2],
                        s == null ? "NULL" : escape(s)
                    );
                }
            }
            String family = (naming == null) ? null : naming.getFontFamily();
            String subfamily = (naming == null) ? null : naming.getFontSubFamily();
            String psname = (naming == null) ? null : naming.getPostScriptName();
            out.printf("FAMILY\t%s%n", family == null ? "NULL" : escape(family));
            out.printf("SUBFAMILY\t%s%n", subfamily == null ? "NULL" : escape(subfamily));
            out.printf("PSNAME\t%s%n", psname == null ? "NULL" : escape(psname));
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }

    /**
     * Replace bytes that would break the tab-delimited line format (TAB, CR,
     * LF) with backslash escapes so a copyright record that spans multiple
     * lines stays on a single output line. Backslash itself is escaped so the
     * mapping is unambiguous and pypdfbox can reproduce it.
     */
    private static String escape(String s) {
        StringBuilder b = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\') {
                b.append("\\\\");
            } else if (c == '\t') {
                b.append("\\t");
            } else if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
