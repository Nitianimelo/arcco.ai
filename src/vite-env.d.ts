/// <reference types="vite/client" />

declare module '*.mjs?url' {
    const content: string;
    export default content;
}
