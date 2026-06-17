import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Calendar;
import java.util.Date;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.SignatureInterface;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.cert.jcajce.JcaX509v3CertificateBuilder;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.CMSTypedData;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;

/**
 * Live oracle probe: Apache PDFBox signs a PDF with a self-signed cert.
 *
 * Mints an RSA-2048 self-signed certificate in-process (BouncyCastle, no
 * keystore on disk), loads the input PDF, attaches a PDSignature via
 * PDDocument.addSignature(...) wired to a SignatureInterface whose sign()
 * produces a detached CMS (adbe.pkcs7.detached) SignedData blob over the
 * bracketed /ByteRange bytes, then saveIncremental's the result.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SignProbe in.pdf out.pdf
 * Output (stdout, one key=value per line):
 *   subject=<RFC2253 subject DN>
 *   serial=<decimal serial>
 * The signed PDF is written to out.pdf.
 */
public final class SignProbe {

    private static final String SUBJECT_DN = "CN=oracle-sign-probe,O=pypdfbox-oracle,C=US";

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        File in = new File(args[0]);
        File outFile = new File(args[1]);

        // ---- mint self-signed RSA-2048 cert ----
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        KeyPair kp = kpg.generateKeyPair();
        final PrivateKey privateKey = kp.getPrivate();

        BigInteger serial = BigInteger.valueOf(System.currentTimeMillis());
        Calendar cal = Calendar.getInstance();
        Date notBefore = new Date(cal.getTimeInMillis() - 60_000L);
        cal.add(Calendar.DAY_OF_YEAR, 1);
        Date notAfter = cal.getTime();
        X500Name dn = new X500Name(SUBJECT_DN);

        JcaX509v3CertificateBuilder certBuilder = new JcaX509v3CertificateBuilder(
                dn, serial, notBefore, notAfter, dn, kp.getPublic());
        ContentSigner certSigner = new JcaContentSignerBuilder("SHA256withRSA")
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .build(privateKey);
        X509CertificateHolder holder = certBuilder.build(certSigner);
        final X509Certificate certificate = new JcaX509CertificateConverter()
                .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                .getCertificate(holder);

        // ---- detached CMS signer wired into PDFBox's signing pipeline ----
        SignatureInterface signer = new SignatureInterface() {
            @Override
            public byte[] sign(InputStream content) throws java.io.IOException {
                try {
                    byte[] data = content.readAllBytes();
                    CMSTypedData typed = new CMSProcessableByteArray(data);
                    CMSSignedDataGenerator gen = new CMSSignedDataGenerator();
                    ContentSigner sha256Signer =
                            new JcaContentSignerBuilder("SHA256withRSA")
                                    .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                    .build(privateKey);
                    gen.addSignerInfoGenerator(
                            new JcaSignerInfoGeneratorBuilder(
                                    new JcaDigestCalculatorProviderBuilder()
                                            .setProvider(BouncyCastleProvider.PROVIDER_NAME)
                                            .build())
                                    .build(sha256Signer, certificate));
                    gen.addCertificates(new JcaCertStore(
                            java.util.Collections.singletonList(certificate)));
                    // detached: do NOT carry the document bytes inside the blob.
                    CMSSignedData signed = gen.generate(typed, false);
                    return signed.getEncoded();
                } catch (Exception e) {
                    throw new java.io.IOException(e);
                }
            }
        };

        // Load the original from `in`; saveIncremental writes the full file
        // (original revision + appended signed revision) to `out`. PDFBox
        // requires the document to have been loaded from a file/bytes so the
        // original revision can be replayed ahead of the increment.
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDSignature signature = new PDSignature();
            signature.setFilter(PDSignature.FILTER_ADOBE_PPKLITE);
            signature.setSubFilter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED);
            signature.setName("Oracle Sign Probe");
            signature.setReason("differential parity");
            signature.setSignDate(Calendar.getInstance());

            doc.addSignature(signature, signer);

            try (OutputStream os = Files.newOutputStream(outFile.toPath(),
                    java.nio.file.StandardOpenOption.CREATE,
                    java.nio.file.StandardOpenOption.TRUNCATE_EXISTING,
                    java.nio.file.StandardOpenOption.WRITE)) {
                doc.saveIncremental(os);
            }
        }

        out.println("subject=" + certificate.getSubjectX500Principal().getName());
        out.println("serial=" + certificate.getSerialNumber().toString());
    }
}
