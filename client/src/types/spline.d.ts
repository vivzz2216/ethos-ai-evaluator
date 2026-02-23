declare namespace JSX {
  interface IntrinsicElements {
    'spline-viewer': {
      url: string;
      style?: React.CSSProperties;
      onError?: (e: any) => void;
      onLoad?: () => void;
    };
  }
}
