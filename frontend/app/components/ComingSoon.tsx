import Link from "next/link";
import Navbar from "./Navbar";
import styles from "./ComingSoon.module.css";

interface Props {
  title: string;
  blurb: string;
}

export default function ComingSoon({ title, blurb }: Props) {
  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.inner}>
          <div className={styles.flourish}>
            <span className={styles.line}></span>
            <span className={styles.diamond}></span>
            <span className={`${styles.diamond} ${styles.center}`}></span>
            <span className={styles.diamond}></span>
            <span className={styles.line}></span>
          </div>
          <p className={styles.eyebrow}>Coming Soon</p>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.blurb}>{blurb}</p>
          <Link href="/" className={styles.back}>← Back to home</Link>
        </div>
      </main>
    </>
  );
}
