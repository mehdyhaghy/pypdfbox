import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cff.CFFCharset;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;

// Live oracle probe for fontbox CFF /charset resolution -- the
// CFFFont.getCharset() surface. Covers all three on-disk charset
// encodings (Format0 = array of SIDs, Format1 = ranges with 1-byte
// nLeft, Format2 = ranges with 2-byte nLeft) plus the predefined
// charsets (ISOAdobe = 0, Expert = 1, ExpertSubset = 2), for both
// name-keyed (Type1C) and CID-keyed CFF programs.
//
// The sibling CffEncodingProbe owns the Top DICT /Encoding surface
// (getEncoding()); CffCidFdProbe owns /FDSelect + /FDArray;
// CffMetadataProbe owns ROS / name / version strings. This probe owns
// the GID->name (Type1, via SID->string) and GID->CID (CID-keyed)
// charset mapping with no overlap.
//
//   java -cp ... CffCharsetProbe <input.cff>
//
// Output (UTF-8, stdout, tab-delimited, deterministic GID order):
//
//   FONT   baseFontClass            CFFFont.getClass().getSimpleName()
//   CID    isCIDFont                CFFCharset.isCIDFont()
//   NGLYPH count                    number of charstrings (GID range)
//
//   NAME-keyed font, per GID:
//     NAME gid name                 getNameForGID(gid)
//     SID  gid sid                  getSIDForGID(gid)
//     GFS  sid gid                  getGIDForSID(sid) round-trip
//     GSID name sid                 getSID(name) round-trip
//
//   CID-keyed font, per GID:
//     CIDG gid cid                  getCIDForGID(gid)
//     GFC  cid gid                  getGIDForCID(cid) round-trip
//
// Never mutates the input; closes the stream via try-with-resources.
public final class CffCharsetProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffCharsetProbe <input.cff>");
            return;
        }
        read(out, args[0]);
    }

    private static void read(PrintStream out, String path) throws Exception {
        byte[] data;
        try (FileInputStream fis = new FileInputStream(new File(path))) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            data = bos.toByteArray();
        }
        final byte[] payload = data;
        CFFFont font = new CFFParser().parse(payload,
                new CFFParser.ByteSource() {
                    @Override
                    public byte[] getBytes() {
                        return payload;
                    }
                }).get(0);
        out.printf("FONT\t%s%n", font.getClass().getSimpleName());

        CFFCharset charset = font.getCharset();
        out.printf("CID\t%s%n", charset.isCIDFont());

        int nGlyphs = font.getCharStringBytes().size();
        out.printf("NGLYPH\t%d%n", nGlyphs);

        if (charset.isCIDFont()) {
            for (int gid = 0; gid < nGlyphs; gid++) {
                int cid = charset.getCIDForGID(gid);
                out.printf("CIDG\t%d\t%d%n", gid, cid);
                int back = charset.getGIDForCID(cid);
                out.printf("GFC\t%d\t%d%n", cid, back);
            }
        } else {
            for (int gid = 0; gid < nGlyphs; gid++) {
                String name = charset.getNameForGID(gid);
                out.printf("NAME\t%d\t%s%n", gid, name);
                int sid = charset.getSIDForGID(gid);
                out.printf("SID\t%d\t%d%n", gid, sid);
                out.printf("GFS\t%d\t%d%n", sid, charset.getGIDForSID(sid));
                if (name != null) {
                    out.printf("GSID\t%s\t%d%n", name, charset.getSID(name));
                }
            }
        }
    }
}
