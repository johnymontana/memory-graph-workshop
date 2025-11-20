/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    config.externals = config.externals || []
    config.externals.push({
      'utf-8-validate': 'commonjs utf-8-validate',
      'bufferutil': 'commonjs bufferutil',
    })
    
    // Add fallback for cytoscape to resolve import issues
    config.resolve.alias = {
      ...config.resolve.alias,
      'cytoscape': require.resolve('cytoscape'),
    }
    
    // Handle cytoscape as external to avoid bundling issues
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      }
    }
    
    return config
  },
  transpilePackages: [
    '@neo4j-nvl/base',
    '@neo4j-nvl/react',
    '@neo4j-nvl/layout-workers',
  ],
}

module.exports = nextConfig
