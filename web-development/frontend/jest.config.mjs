/** Jest 엄격 모드: lib 단위 테스트 + 커버리지 임계값 */
/** @type {import('jest').Config} */
export default {
  testEnvironment: 'node',
  roots: ['<rootDir>'],
  testMatch: ['**/__tests__/**/*.test.ts', '**/*.test.ts'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transform: {
    '^.+\\.(ts|tsx)$': ['ts-jest', { tsconfig: { module: 'commonjs' } }],
  },
  collectCoverageFrom: ['lib/**/*.ts', '!lib/**/*.d.ts'],
  coverageThreshold: {
    global: {
      branches: 45,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  testPathIgnorePatterns: ['/node_modules/', '/.next/'],
  verbose: true,
};
