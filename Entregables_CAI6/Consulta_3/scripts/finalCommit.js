const { ethers } = require("hardhat");

const AUCTION_ADDRESS = process.env.AUCTION_ADDRESS;

const BIDS = [
  {
    name: "Proveedor A",
    privateKey: process.env.PROVIDER_A_PRIVATE_KEY,
    amount: ethers.parseEther("0.001"),
    deposit: ethers.parseEther("0.0001"),
    secret: "cai6FinalA",
  },
  {
    name: "Proveedor B",
    privateKey: process.env.PROVIDER_B_PRIVATE_KEY,
    amount: ethers.parseEther("0.0008"),
    deposit: ethers.parseEther("0.00008"),
    secret: "cai6FinalB",
  },
  {
    name: "Proveedor C",
    privateKey: process.env.PROVIDER_C_PRIVATE_KEY,
    amount: ethers.parseEther("0.0012"),
    deposit: ethers.parseEther("0.00012"),
    secret: "cai6FinalC",
  },
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function dateFromUnix(ts) {
  return new Date(Number(ts) * 1000).toISOString();
}

async function main() {
  if (!AUCTION_ADDRESS) {
    throw new Error("Falta AUCTION_ADDRESS en .env");
  }

  const auction = await ethers.getContractAt(
    "HealthProcurementAuction",
    AUCTION_ADDRESS
  );

  const auctionStart = await auction.auctionStart();
  const biddingDeadline = await auction.biddingDeadline();

  let block = await ethers.provider.getBlock("latest");
  let now = BigInt(block.timestamp);

  console.log("Auction:", AUCTION_ADDRESS);
  console.log("Ahora:", now.toString(), dateFromUnix(now));
  console.log("auctionStart:", auctionStart.toString(), dateFromUnix(auctionStart));
  console.log("biddingDeadline:", biddingDeadline.toString(), dateFromUnix(biddingDeadline));

  if (now < auctionStart) {
    const waitSeconds = Number(auctionStart - now + 3n);
    console.log(`Esperando ${waitSeconds} segundos hasta auctionStart...`);
    await sleep(waitSeconds * 1000);
  }

  block = await ethers.provider.getBlock("latest");
  now = BigInt(block.timestamp);

  if (now >= biddingDeadline) {
    throw new Error("La fase commit ya ha terminado. Despliega otra Auction.");
  }

  console.log("\n=== COMMIT BIDS ===");

  for (const bid of BIDS) {
    const wallet = new ethers.Wallet(bid.privateKey, ethers.provider);

    const commitHash = ethers.solidityPackedKeccak256(
      ["uint256", "string"],
      [bid.amount, bid.secret]
    );

    console.log(`\n${bid.name}`);
    console.log("Wallet:", wallet.address);
    console.log("Amount wei:", bid.amount.toString());
    console.log("Amount ETH:", ethers.formatEther(bid.amount));
    console.log("Deposit wei:", bid.deposit.toString());
    console.log("Deposit ETH:", ethers.formatEther(bid.deposit));
    console.log("Secret:", bid.secret);
    console.log("Commit hash:", commitHash);

    const tx = await auction.connect(wallet).commitBid(commitHash, {
      value: bid.deposit,
    });

    console.log("commitBid tx:", tx.hash);
    await tx.wait();
    console.log("commitBid confirmado");

    const b = await auction.bidders(wallet.address);

    console.log("On-chain commitHash:", b.commitHash);
    console.log("On-chain deposit:", b.deposit.toString());
    console.log("committed:", b.committed);
    console.log("hasRevealed:", b.hasRevealed);

    if (b.commitHash.toLowerCase() !== commitHash.toLowerCase()) {
      throw new Error(`${bid.name}: el hash guardado NO coincide`);
    }

    console.log("Hash comprobado correctamente");
  }

  const totalCommitted = await auction.totalCommitted();
  console.log("\nTotal committed:", totalCommitted.toString());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});